# deep_research.py
import asyncio
import json
from api import create_api_instance
from api.firecrawl_api import FirecrawlAPI
from utils.slice_chunks import slice_prompt_context_aware
from prompt import system_prompt

llm_client = create_api_instance("openai")
firecrawl_client = FirecrawlAPI()


async def generate_feedback(query: str) -> list:
    """Generates follow-up questions to clarify research direction."""
    response = await llm_client.generate_text(
        prompt=[
            {"role": "system", "content": system_prompt()},
            {
                "role": "user",
                "content": (
                    f"Given this research topic: {query}, generate 3-5 follow-up questions to "
                    "better understand the user's research needs. Return the response as a JSON "
                    "object with a 'questions' array field."
                ),
            },
        ],
    )
    try:
        parsed = json.loads(response)
        questions = parsed.get("questions", [])
        if not questions:
            return []
        
        if isinstance(questions[0], dict):
            questions_list = []
            for q in questions:
                questions_list.append(q["question"])
            return questions_list
        else:
            return questions
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON in generate_feedback: {e}")
        print(f"Raw response: {response}")
        return []


async def generate_serp_queries(
    query: str, num_queries: int = 3, learnings: list = None
) -> list:
    """Generate SERP queries based on user input and previous learnings."""
    prompt_text = (
        f"Given the following prompt from the user, generate a list of SERP queries to research the topic. "
        f"Return a JSON object with a 'queries' array field containing {num_queries} queries (or less if the original prompt is clear). "
        "Each query object should have 'query' and 'research_goal' fields. Make sure each query is unique and not similar to each other: "
        f"<prompt>{query}</prompt>"
    )
    if learnings:
        prompt_text += (
            "\n\nHere are some learnings from previous research, use them to generate more specific queries: "
            + " ".join(learnings)
        )
    response = await llm_client.generate_text(
        prompt=[
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prompt_text},
        ],
    )
    try:
        parsed = json.loads(response)
        return parsed.get("queries", [])
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON in generate_serp_queries: {e}")
        print(f"Raw response: {response}")
        return []


async def process_serp_result(query: str, result: dict, num_learnings: int = 3, num_follow_up_questions: int = 3) -> dict:
    """Process search results to extract learnings and follow-up questions."""
    contents = [
        slice_prompt_context_aware(item.get("markdown", ""), 25000)
        for item in result.get("data", [])
        if item.get("markdown")
    ]
    contents_str = "".join(f"<content>\n{content}\n</content>" for content in contents)
    prompt_text = (
        f"Given the following contents from a SERP search for the query <query>{query}</query>, "
        f"generate a list of learnings from the contents. Return a JSON object with 'learnings' "
        f"and 'followUpQuestions' arrays. Include up to {num_learnings} learnings and "
        f"{num_follow_up_questions} follow-up questions. The learnings should be unique, "
        "concise, and information-dense, including entities, metrics, numbers, and dates.\n\n"
        f"<contents>{contents_str}</contents>"
    )
    response = await llm_client.generate_text(
        prompt=[
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": prompt_text},
        ],
    )
    try:
        parsed = json.loads(response)
        return parsed
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON in process_serp_result: {e}")
        print(f"Raw response: {response}")
        return {"learnings": [], "followUpQuestions": []}


async def write_final_report(prompt: str, learnings: list, visited_urls: list) -> str:
    """Generate final report based on all research learnings."""
    learnings_string = slice_prompt_context_aware(
        "\n".join([f"<learning>\n{learning}\n</learning>" for learning in learnings]),
        150000,
    )
    user_prompt = (
        f"Given the following prompt from the user, write a final report on the topic using "
        "the learnings from research. Return a JSON object with a 'reportMarkdown' field "
        "containing a detailed markdown report (aim for 3+ pages). Include ALL the learnings "
        "from research:\n\n"
        f"<prompt>{prompt}</prompt>\n\n"
        "Here are all the learnings from research:\n\n"
        f"<learnings>\n{learnings_string}\n</learnings>"
    )

    response = await llm_client.generate_text(
        prompt=[
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
    )
    try:
        parsed = json.loads(response)
        report = parsed.get("reportMarkdown", "")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON in write_final_report: {e}")
        print(f"Raw response: {response}")
        report = response

    urls_section = "\n\n## Sources\n\n" + "\n".join(
        [f"- {url}" for url in visited_urls]
    )
    return report + urls_section


async def deep_research(
    query: str,
    breadth: int,
    depth: int,
    concurrency: int,
    learnings: list = None,
    visited_urls: list = None,
):
    learnings = learnings or []
    visited_urls = visited_urls or []

    serp_queries = await generate_serp_queries(
        query=query, num_queries=breadth, learnings=learnings
    )
    semaphore = asyncio.Semaphore(concurrency)
    async def process_query(serp_query: dict):
        async with semaphore:
            retry_count = 0
            MAX_RETRIES = 5
            TIMEOUT = 15
            while retry_count < MAX_RETRIES:
                try:
                    result = await firecrawl_client.search(
                        serp_query.get("query"), timeout=TIMEOUT, limit=5
                    )
                    break  # if successful, break out of the retry loop
                except Exception as e:
                    if "429" in str(e):
                        retry_count += 1
                    else:
                        print(f"Error running query: {serp_query.get('query')}: {e}")
                        return {"learnings": [], "visited_urls": []}
                await asyncio.sleep(3)
            else:
                print(f"Max retries exceeded for query: {serp_query.get('query')}")
                return {"learnings": [], "visited_urls": []}
            
            # Process the result if successful
            new_urls = [
                item.get("url")
                for item in result.get("data", [])
                if item.get("url")
            ]

            new_breadth = max(1, breadth // 2)
            new_depth = depth - 1

            new_learnings = await process_serp_result(
                query=serp_query.get("query"),
                result=result,
                num_follow_up_questions=new_breadth,
            )

            # Convert each learning to a string if necessary
            current_learnings = [
                learning if isinstance(learning, str) else str(learning)
                for learning in new_learnings.get("learnings", [])
            ]
            all_learnings = learnings + current_learnings
            all_urls = visited_urls + new_urls

            if new_depth > 0:
                print(
                    f"Researching deeper, breadth: {new_breadth}, depth: {new_depth}"
                )
                next_query = (
                    f"Previous research goal: {serp_query.get('research_goal')}\n"
                    f"Follow-up research directions: {' '.join(new_learnings.get('followUpQuestions', []))}"
                ).strip()
                return await deep_research(
                    query=next_query,
                    breadth=new_breadth,
                    depth=new_depth,
                    concurrency=concurrency,
                    learnings=all_learnings,
                    visited_urls=all_urls,
                )
            return {"learnings": all_learnings, "visited_urls": all_urls}

    results = await asyncio.gather(*[process_query(q) for q in serp_queries])

    # When combining, ensure all learnings are hashable (e.g., strings)
    all_learnings = list(
        set(
            learning if isinstance(learning, str) else str(learning)
            for result in results
            for learning in result.get("learnings", [])
        )
    )
    all_urls = list(
        set(url for result in results for url in result.get("visited_urls", []))
    )
    return {"learnings": all_learnings, "visited_urls": all_urls}
