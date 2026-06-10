"""
app.py

Gradio web interface for the campus survival guide RAG pipeline.

Run:
    python app.py
    # then open http://localhost:7860

Requires GROQ_API_KEY in your .env file (or exported in the shell).
"""

from dotenv import load_dotenv

load_dotenv()  # must run before importing query so the key is available

import gradio as gr

from query import ask


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handle_query(question: str) -> tuple[str, str]:
    """Gradio handler: returns (answer_text, sources_text)."""
    question = question.strip()
    if not question:
        return "Please enter a question.", ""

    try:
        result = ask(question)
    except EnvironmentError as exc:
        return f"Configuration error: {exc}", ""
    except FileNotFoundError as exc:
        return f"Index not found: {exc}", ""
    except Exception as exc:
        return f"Error: {exc}", ""

    answer = result["answer"]
    sources_text = "\n".join(result["sources"])
    return answer, sources_text


# ---------------------------------------------------------------------------
# Example questions (from planning.md §Evaluation Plan)
# ---------------------------------------------------------------------------

EXAMPLES = [
    ["What do students say about dorm safety at night?"],
    ["Tips for managing stress and mental health in college?"],
    ["How do I find free food and resources on campus?"],
    ["What do students recommend for dorm room essentials?"],
    ["What free late-night transportation is available at UW Oshkosh?"],
]


# ---------------------------------------------------------------------------
# UI layout
# ---------------------------------------------------------------------------

with gr.Blocks(title="Campus Survival Guide") as demo:

    gr.Markdown(
        """
        # 🎓 Campus Survival Guide
        **Ask anything about college life.** Answers are grounded in real student reviews,
        Reddit threads, campus newspapers, and peer advice — not generic AI knowledge.
        Every claim is cited to its source.
        """
    )

    with gr.Row():
        with gr.Column(scale=2):
            inp = gr.Textbox(
                label="Your question",
                placeholder="e.g. What do students recommend for staying safe walking home at night?",
                lines=2,
            )
            with gr.Row():
                btn  = gr.Button("Ask", variant="primary")
                clear = gr.ClearButton([inp], value="Clear")

            gr.Examples(
                examples=EXAMPLES,
                inputs=inp,
                label="Try an example",
            )

        with gr.Column(scale=3):
            answer_box = gr.Textbox(
                label="Answer",
                lines=12,

                interactive=False,
            )
            sources_box = gr.Textbox(
                label="Retrieved from (top-5 chunks)",
                lines=6,

                interactive=False,
            )

    gr.Markdown(
        "_Answers are based solely on the 12 student-sourced documents in this "
        "corpus. If the documents don't cover your question, the system will say so._"
    )

    # Wire up interactions
    btn.click(handle_query,  inputs=inp, outputs=[answer_box, sources_box])
    inp.submit(handle_query, inputs=inp, outputs=[answer_box, sources_box])


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
