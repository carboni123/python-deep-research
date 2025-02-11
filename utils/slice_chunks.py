import re
import tiktoken

# Minimum number of characters for a prompt chunk.
MIN_CHUNK_SIZE = 140

# Initialize the encoder using OpenAI's current encoding.
encoder = tiktoken.get_encoding("cl100k_base")

def slice_prompt_context_aware(prompt: str, context_size: int) -> str:
    """
    Slices the prompt so that its tokenized length does not exceed context_size,
    but only cuts at natural sentence boundaries. If even a single sentence exceeds
    the token limit, falls back to a simple token slice.
    """
    tokens = encoder.encode(prompt)
    if len(tokens) <= context_size:
        return prompt

    # Split the text into sentences using a regular expression.
    # This pattern splits on punctuation (. ! ?) followed by whitespace.
    sentences = re.split(r'(?<=[.!?])\s+', prompt)

    accumulated = ""
    for sentence in sentences:
        # Append the sentence with a trailing space.
        candidate = accumulated + sentence + " "
        candidate_tokens = encoder.encode(candidate)
        if len(candidate_tokens) > context_size:
            # If adding this sentence would exceed the limit, stop.
            # If nothing has been added yet, fall back to token slicing.
            if not accumulated.strip():
                # Fall back: slice tokens directly and decode them.
                sliced_tokens = tokens[:context_size]
                return encoder.decode(sliced_tokens)
            break
        accumulated = candidate

    return accumulated.strip()
