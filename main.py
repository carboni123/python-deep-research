import asyncio
import argparse
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint

from deep_research import generate_feedback, deep_research, write_final_report

console = Console()

async def main(concurrency: int):
    """Deep Research CLI"""
    console.print(
        Panel.fit(
            "[bold blue]Deep Research Assistant[/bold blue]\n"
            "[dim]An AI-powered research tool[/dim]"
        )
    )

    # Use console.input for colored prompts.
    query = console.input("\nWhat would you like to research? ")
    console.print()

    breadth_prompt = "Research breadth (recommended 2-10) [4]: "
    breadth_input = console.input(breadth_prompt)
    breadth = int(breadth_input.strip() or "4")
    console.print()

    depth_prompt = "Research depth (recommended 1-5) [2]: "
    depth_input = console.input(depth_prompt)
    depth = int(depth_input.strip() or "2")
    console.print()

    # Show progress messages via simple prints.
    console.print("\n[yellow]Creating research plan... Please wait.[/yellow]")
    follow_up_questions = await generate_feedback(query)

    console.print("\n[bold yellow]Follow-up Questions:[/bold yellow]")
    answers = []
    for i, question in enumerate(follow_up_questions, 1):
        console.print(f"\n[bold blue]Q{i}:[/bold blue] {question}")
        answer = console.input("[cyan]Your answer: [/cyan]")
        answers.append(answer)
        console.print()

    # Combine information for research.
    combined_query = f"""
    Initial Query: {query}
    Follow-up Questions and Answers:
    {chr(10).join(f"Q: {q} A: {a}" for q, a in zip(follow_up_questions, answers))}
    """

    console.print("[yellow]Researching your topic... Please wait.[/yellow]")
    research_results = await deep_research(
        query=combined_query,
        breadth=breadth,
        depth=depth,
        concurrency=concurrency,
    )

    console.print("\n[yellow]Learnings:[/yellow]")
    for learning in research_results["learnings"]:
        rprint(f"• {learning}")

    console.print("[yellow]Writing final report... Please wait.[/yellow]")
    report = await write_final_report(
        prompt=combined_query,
        learnings=research_results["learnings"],
        visited_urls=research_results["visited_urls"],
    )

    console.print("\n[bold green]Research Complete![/bold green]")
    console.print("\n[yellow]Final Report:[/yellow]")
    console.print(Panel(report, title="Research Report"))

    console.print("\n[yellow]Sources:[/yellow]")
    for url in research_results["visited_urls"]:
        rprint(f"• {url}")

    with open("output.md", "w", encoding="utf-8") as f:
        f.write(report)
    console.print("\n[dim]Report has been saved to output.md[/dim]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deep Research CLI")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent tasks, depending on your API rate limits."
    )
    args = parser.parse_args()
    asyncio.run(main(args.concurrency))
