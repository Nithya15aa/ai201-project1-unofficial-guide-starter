"""
generate.py

Generation stage for the campus survival guide RAG pipeline.

Architecture (from planning.md):
    Retrieval → Generation
    Model : llama-3.3-70b-versatile via Groq API (free tier)
    Input : query + top-5 retrieved chunks from embed_retrieve.retrieve()
    Output: grounded, cited response — answers only from provided documents

Grounding contract
------------------
The prompt enforces a hard constraint: the model may ONLY use text that
appears verbatim in the numbered sources. It is explicitly told NOT to draw
on training knowledge and to say "I don't have enough information" if the
documents are insufficient. Source attribution ([Source N]) is required for
every claim, so it is programmatically verifiable — not left to the model's
discretion.
"""

import os
from datetime import date

from groq import Groq

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENERATION_MODEL = "llama-3.3-70b-versatile"
_STALENESS_YEARS = 3          # flag chunks older than this (planning.md §Anticipated Challenges)
MAX_TOKENS = 1024


# ---------------------------------------------------------------------------
# 1. Prompt builder
# ---------------------------------------------------------------------------

# The system message is separated from user content so the grounding
# constraint sits in the highest-priority slot for instruction-tuned models.
_SYSTEM_MESSAGE = """\
You are a helpful assistant for college students.

CRITICAL RULES — follow all of them without exception:
1. Answer using ONLY the numbered source excerpts provided in the user message.
2. Do NOT use your training knowledge. If the sources don't contain the answer, say exactly:
   "I don't have enough information in the provided documents to answer that question."
3. Every factual claim in your answer MUST include an inline citation: (Source 1), (Source 2), etc.
4. Do not combine or extrapolate beyond what the sources say.
5. If a source is marked [POSSIBLY OUTDATED], include that caveat when you cite it.
"""


def build_prompt(query: str, chunks: list[dict]) -> str:
    """Construct the grounded-answer user message from a query and retrieved chunks.

    Args:
        query  : The user's natural-language question.
        chunks : List of chunk dicts from retrieve(), each containing:
                 text, chunk_id, source_type, url, published_date, score.

    Returns:
        The user-turn string to send alongside _SYSTEM_MESSAGE.
    """
    today = date.today()
    cutoff_year = today.year - _STALENESS_YEARS

    source_blocks: list[str] = []

    for i, chunk in enumerate(chunks, 1):
        source_type = chunk.get("source_type", "unknown")
        url = chunk.get("url", "")
        published_date = chunk.get("published_date", "")
        text = chunk.get("text", "").strip()

        # Staleness flag — parsed from "2024" or "2016-06-01" format
        stale_tag = ""
        try:
            pub_year = int(str(published_date).split("-")[0])
            if pub_year < cutoff_year:
                stale_tag = f" [POSSIBLY OUTDATED — published {pub_year}]"
        except (ValueError, AttributeError):
            pass

        header = f"[Source {i}] {source_type} | {url}{stale_tag}"
        source_blocks.append(f"{header}\n{text}")

    sources_section = "\n\n".join(source_blocks)

    return (
        f"SOURCES:\n\n{sources_section}\n\n"
        f"---\n\n"
        f"Question: {query}\n\n"
        "Answer (cite every claim with [Source N]; "
        "if the sources don't cover this, say you don't have enough information):"
    )


# ---------------------------------------------------------------------------
# 2. Generate
# ---------------------------------------------------------------------------

def generate(query: str, chunks: list[dict]) -> str:
    """Call Groq and return the model's grounded response text.

    Reads GROQ_API_KEY from the environment (set via .env + python-dotenv,
    or exported directly).

    Args:
        query  : The user's natural-language question.
        chunks : Retrieved chunks from retrieve().

    Returns:
        The model's response as a plain string.

    Raises:
        EnvironmentError: If GROQ_API_KEY is not set.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Add it to your .env file or run: export GROQ_API_KEY=gsk_..."
        )

    client = Groq(api_key=api_key)
    user_message = build_prompt(query, chunks)

    completion = client.chat.completions.create(
        model=GENERATION_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=0.2,          # low temp = less improvisation, better grounding
        messages=[
            {"role": "system", "content": _SYSTEM_MESSAGE},
            {"role": "user",   "content": user_message},
        ],
    )

    return completion.choices[0].message.content
