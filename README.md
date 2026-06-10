# The Unofficial Guide — Project 1

---

## Domain

This system covers peer-generated campus survival advice — the practical,
experience-based knowledge that students share informally but that never
appears in official university guides. This includes tips on dorm living,
late-night safety, mental health accommodations, free campus resources,
and course selection strategy.

Official university channels (admissions pages, orientation packets, course
catalogs) are written to present the institution favorably. They describe
what services exist but not whether those services are actually useful, hard
to access, or unknown to most students. Peer sources fill that gap: a Reddit
thread will tell you the dining hall runs out of food after 7pm, that the
free campus ride service is called UWO-Go, or that you can request a single
dorm room through disability services. None of that appears in any official
guide.

---

## Document Sources

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | r/college (Reddit) | Reddit forum | https://www.reddit.com/r/college/ |
| 2 | Niche.com student reviews | Review site | https://www.niche.com/colleges/search/best-student-life/ |
| 3 | RateMyProfessors | Review site | https://www.ratemyprofessors.com |
| 4 | The Daily Pennsylvanian — dorm tips | Campus newspaper | https://www.thedp.com/article/2016/06/new-student-issue-tips-dorm-living |
| 5 | Advance-Titan — freshman survival guide | Campus newspaper | https://advancetitan.com/opinion/2024/09/03/freshman-survival-guide |
| 6 | UMass SBS Pathways Blog | Student blog | https://sbspathways.umass.edu/blog/2022/08/31/what-i-wish-id-known-advice-from-juniors-seniors-and-new-grads/ |
| 7 | Her Campus LMU — hidden perks | Student blog | https://www.hercampus.com/school/lmu/hidden-perks-being-college-student/ |
| 8 | NBC News — "13 Things I Wish I Knew" | News article | https://www.nbcnews.com/feature/freshman-year/keep-calm-study-13-things-i-wish-i-knew-freshman-n399641 |
| 9 | Unigo.com student reviews | Review site | https://www.unigo.com/colleges |
| 10 | Quora — valuable college experiences | Q&A forum | https://www.quora.com/What-are-some-of-the-most-valuable-experiences-a-college-student-should-not-miss-out-on |
| 11 | YouTube — College Survival Guide video | Video transcript | https://www.youtube.com/watch?v=c58yVp_j55Q |
| 12 | Alex's Declassified College Survival Guide | Student blog | https://www.familyaware.org/alexs-declassified-college-survival-guide/ |

---

## Chunking Strategy

**Chunk size:** 400 tokens

**Overlap:** 50 tokens

**Why these choices fit your documents:**
The corpus is made up of short-form conversational writing — Reddit comments,
review snippets, blog paragraphs, and Q&A answers. Each paragraph or list item
typically contains one complete piece of advice, making 400 tokens a natural
fit: large enough to preserve context within a single tip, small enough to avoid
blending unrelated advice from different parts of the same post.

A 50-token overlap prevents tips from being severed at chunk boundaries. Student
writing frequently uses sequential connectors ("Also…", "On top of that…"), so
a small overlap ensures those continuations are not orphaned in the next chunk.

Before chunking, each document was cleaned with a custom `clean_markdown()`
function that stripped heading markers (`###`), bold/italic formatting (`**`),
inline code, and markdown links. A boilerplate filter then removed any chunk
containing ad disclosures, cookie notices, or navigation text. A minimum word
filter (25 words) removed sentence fragments produced by boundary splits.

`RecursiveCharacterTextSplitter` from LangChain was used with separators
`["\n\n", "\n", ". "]` in that priority order, so the splitter respects
paragraph structure before falling back to sentence or word boundaries.

**Final chunk count:** 174 chunks across 12 documents

---

## Embedding Model

**Model used:** `sentence-transformers/all-MiniLM-L6-v2`

**Production tradeoff reflection:**
`all-MiniLM-L6-v2` is fast, lightweight, and performs well on short
conversational text, which matches this corpus. Its 256-token context window
is not a limitation here because chunks are capped at 400 characters and the
meaningful content of any single tip fits well within that limit. For a
research prototype with a small corpus, the speed and zero API cost make it
the right starting point.

In a production deployment, the primary tradeoffs to weigh would be domain
specificity and context length. General-purpose models are not trained on
student slang or campus vocabulary — terms like "meal swipe," "flex dollars,"
"blue light station," or "RA" may not embed meaningfully. A model fine-tuned
on student-generated text, or re-ranked with a cross-encoder on top of initial
retrieval, would likely improve precision on niche queries. For a corpus that
expanded to include full blog posts or long Reddit threads, a model with a
longer context window such as `text-embedding-3-large` (8,191 tokens) would
handle larger chunks without requiring re-chunking. Latency is a minor concern
at this corpus size but would matter at scale; a two-stage approach — fast ANN
retrieval with a small model, followed by cross-encoder re-ranking on the top
20 — balances accuracy and speed for real users.

---

## Grounded Generation

**System prompt grounding instruction:**
The model was instructed with the following prompt structure:
**How source attribution is surfaced in the response:**
Each chunk passed to the model is labelled with a `[Source N]` tag that
includes its `source_type`, `url`, `chunk_id`, FAISS distance score, and
`published_date`. The model is instructed to cite these labels inline. After
the generated answer, the system prints a full retrieved sources list showing
all five chunks with their metadata, so users can verify every claim against
the original document.

---

## Evaluation Report

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | What do Penn students say about dorm mattress quality and what do they recommend bringing? | Mattresses are poor quality; students recommend a quality mattress pad. Source: Daily Pennsylvanian | Correctly described mattresses as "a slight step up from a literal plastic box" and recommended a mattress pad. Cited thedp.com. Flagged source as possibly outdated (2016). | Relevant | Accurate |
| 2 | What free late-night transportation do UW Oshkosh students recommend for walking alone at night? | UWO-Go free campus ride service. Source: Advance-Titan | Named UWO-Go correctly. Also surfaced a second tip about calling the UW Oshkosh Police Department for escort, drawn from a different retrieved chunk. | Relevant | Accurate |
| 3 | What specific mental health accommodation did the author of Alex's Declassified College Survival Guide obtain, and what was the outcome? | Single dorm room via disability services; therapist wrote supporting documentation; mental health improved. Source: familyaware.org | "I don't have enough information in the provided documents to answer that question." Retrieved YouTube transcript chunks instead of the correct source. | Off-target | Inaccurate |
| 4 | What do University of Michigan students say about dining hall food quality according to Niche reviews? | Students call for more variety and healthier options. Source: Niche.com | Correctly identified the call for more variety and healthier options, but the response was brief and did not surface specific student quotes. | Relevant | Partially accurate |
| 5 | What do UMass students advise about taking classes outside your major during the first year? | Take the most random and exciting classes you can; do not worry about requirements in year one. Source: UMass SBS Pathways blog | Correct advice retrieved, but the response blended the UMass source with NBC News tips from a different institution, attributing cross-institution advice as if it were unified UMass guidance. | Partially relevant | Partially accurate |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

**Question that failed:**
Q3 — "What specific mental health accommodation did the student author of
Alex's Declassified College Survival Guide obtain, and what was the outcome?"

**What the system returned:**
"I don't have enough information in the provided documents to answer that
question." The five retrieved chunks were all from the YouTube transcript
(`youtube_survival_guide_transcript_4`, `_6`, `_10`) and an unrelated Niche
review, with only one chunk from the correct source (`familyaware_alexs_guide_14`)
— and that chunk was the guide's closing paragraph, which contains no
accommodation detail.

**Root cause (tied to a specific pipeline stage):**
The failure occurred at the retrieval stage, not generation. The correct
information exists in the corpus — chunks `familyaware_alexs_guide_2` through
`familyaware_alexs_guide_10` contain the accommodation detail — but none of
them ranked in the top 5 for this query.

The cause is that `all-MiniLM-L6-v2` encodes semantic meaning rather than
referential identity. The query phrase "Alex's Declassified College Survival
Guide" shares vocabulary with YouTube survival guide content ("college,"
"survival guide," "tips"), so the embedding model ranked YouTube chunks as
closer matches than the actual named source. The model has no mechanism to
treat "Alex's Declassified College Survival Guide" as a proper noun pointing
to a specific document — it is treated as a bag of semantically weighted words.

**What you would change to fix it:**
Add a metadata pre-filter to the retrieval step. When a query contains a named
source title (detectable by matching against the `filename` or `source_type`
metadata fields), restrict the FAISS search to chunks from that source before
running similarity ranking. This would guarantee that queries referencing a
specific document retrieve from that document first, falling back to open search
only if the named source returns no results.

---

## Spec Reflection

**One way the spec helped during implementation:**
The chunking strategy section of `planning.md` specified splitting on
`["\n\n", "\n", ". "]` in priority order, which directly shaped the
`RecursiveCharacterTextSplitter` configuration. More importantly, the spec
defined a concrete validation standard — each chunk should be self-contained
and readable on its own — which made cleaning failures easy to diagnose. When
early chunk samples showed `###` heading markers and `**Answer:**` fragments,
there was a clear standard to test against rather than a vague sense that
something looked wrong. The spec turned debugging into a checklist.

**One way the implementation diverged from the spec, and why:**
The Evaluation Plan in `planning.md` included Q4 as "What do Niche student
reviews say about recurring housing complaints at UC Santa Barbara?" During
data collection, Niche.com blocked automated scraping and the manually
collected sample did not include UC Santa Barbara content. The question was
revised to ask about University of Michigan dining hall food, which was present
in the collected sample. This divergence reveals a practical limitation of
planning evaluation questions before confirming what data is actually
collectable: the spec assumed source content would match the planned questions
exactly, but scraping constraints shaped the real corpus independently of the
plan.

---

## AI Usage

**Instance 1 — generating `collect_data.py`**

- *What I gave the AI:* The full sources table (12 URLs with source types and
  metadata), the two-bucket framework distinguishing scriptable from
  manually-collected sources, and the required output format (`.txt` files
  in `docs/raw/` plus a `sources.json` metadata file).
- *What it produced:* A complete script with a scraping loop, a CSS selector
  fallback chain, boilerplate removal via `tag.decompose()`, and CLI flags
  (`--scrape`, `--validate`, `--instructions`).
- *What I changed or overrode:* The initial CSS selectors for Her Campus and
  Unigo were too specific and returned empty results on those sites. I replaced
  them with broader fallback chains after testing manually. I also added the
  1.5-second sleep between requests, which the first version omitted, to avoid
  rate-limiting.

**Instance 2 — generating `chunk_pipeline.py`**

- *What I gave the AI:* The chunking strategy section from `planning.md`
  (chunk size, overlap, separator order) and the required chunk dict schema
  (six metadata keys plus `chunk_id`).
- *What it produced:* Working `ingest_sources()` and `chunk_text()` functions
  using `RecursiveCharacterTextSplitter`. The `clean_markdown()` and
  `is_boilerplate()` helpers were present but the splitter was called on
  `doc["text"]` (raw text) instead of the cleaned `text` variable, meaning
  the cleaning had no effect on actual chunks.
- *What I changed or overrode:* I caught the bug by inspecting the 5 random
  chunk samples, which still showed `###` and `**Answer:**` artifacts. I
  corrected the variable reference from `doc["text"]` to `text` in the
  `splitter.split_text()` call, and added the boilerplate filter and minimum
  25-word filter that the first version omitted entirely.