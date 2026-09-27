import os
import re
from functools import lru_cache
from pathlib import Path

import faiss
import gradio as gr
import numpy as np
import pdfplumber
import spaces

from huggingface_hub import InferenceClient
from sentence_transformers import SentenceTransformer


# =========================================================
# CONFIG
# =========================================================

SAMPLE_PDF = Path("samples/machine-learning-notes.pdf")

EMBEDDING_MODEL = "BAAI/bge-m3"
GENERATION_MODEL = "Qwen/Qwen3-4B-Instruct-2507"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 75
TOP_K = 3


# =========================================================
# PDF EXTRACTION
# Adapted from original project's extraction.py
# =========================================================

@lru_cache(maxsize=1)
def extract_pdf_sections():
    if not SAMPLE_PDF.exists():
        raise FileNotFoundError(
            f"Sample PDF not found: {SAMPLE_PDF}"
        )

    sections = []

    with pdfplumber.open(SAMPLE_PDF) as pdf:
        for page_number, page in enumerate(
            pdf.pages,
            start=1,
        ):
            text = (page.extract_text() or "").strip()

            if text:
                sections.append(
                    {
                        "text": text,
                        "page_number": page_number,
                        "source_label": f"Page {page_number}",
                    }
                )

    if not sections:
        raise ValueError(
            "The sample PDF does not contain extractable text."
        )

    return sections


# =========================================================
# CHUNKING
# Adapted from original project's chunking.py
# =========================================================

def recursive_split_text(
    text,
    chunk_size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP,
):
    cleaned = re.sub(
        r"\s+",
        " ",
        text or "",
    ).strip()

    if not cleaned:
        return []

    words = cleaned.split()

    if len(words) <= chunk_size:
        return [cleaned]

    step = max(
        1,
        chunk_size - overlap,
    )

    chunks = []

    for start in range(
        0,
        len(words),
        step,
    ):
        part = words[
            start:start + chunk_size
        ]

        if not part:
            break

        chunks.append(
            " ".join(part)
        )

        if start + chunk_size >= len(words):
            break

    return chunks


@lru_cache(maxsize=1)
def build_sample_chunks():
    sections = extract_pdf_sections()

    chunks = []

    for section in sections:
        parts = recursive_split_text(
            section["text"]
        )

        for part in parts:
            chunks.append(
                {
                    "id": len(chunks),
                    "source": section["source_label"],
                    "page_number": section["page_number"],
                    "content": part,
                }
            )

    if not chunks:
        raise ValueError(
            "No chunks were generated from the PDF."
        )

    return chunks


# =========================================================
# EMBEDDING
# Same pattern as original project's embedding.py
# =========================================================

@lru_cache(maxsize=1)
def load_embedding_model():
    return SentenceTransformer(
        EMBEDDING_MODEL,
        device="cuda",
    )


def normalize(vectors):
    vectors = np.asarray(
        vectors,
        dtype="float32",
    )

    norms = np.linalg.norm(
        vectors,
        axis=1,
        keepdims=True,
    )

    norms[norms == 0] = 1

    return (
        vectors / norms
    ).astype("float32")


# =========================================================
# RETRIEVAL
# Same pattern as original FAISS IndexFlatIP retrieval
# =========================================================

@spaces.GPU
def retrieve_context(question):
    question = (question or "").strip()

    if not question:
        return (
            "",
            "Please enter a question.",
        )

    try:
        chunks = build_sample_chunks()
        model = load_embedding_model()

        document_embeddings = model.encode(
            [
                chunk["content"]
                for chunk in chunks
            ],
            batch_size=8,
            show_progress_bar=False,
        )

        document_embeddings = normalize(
            document_embeddings
        )

        index = faiss.IndexFlatIP(
            document_embeddings.shape[1]
        )

        index.add(
            document_embeddings
        )

        query_embedding = model.encode(
            [question],
            show_progress_bar=False,
        )

        query_embedding = normalize(
            query_embedding
        )

        scores, positions = index.search(
            query_embedding,
            min(
                TOP_K,
                len(chunks),
            ),
        )

        retrieved = []
        source_blocks = []

        for rank, (position, score) in enumerate(
            zip(
                positions[0],
                scores[0],
            ),
            start=1,
        ):
            if position < 0:
                continue

            chunk = chunks[
                int(position)
            ]

            item = {
                "source": chunk["source"],
                "content": chunk["content"],
                "score": float(score),
            }

            retrieved.append(item)

            source_blocks.append(
                f"""
### {rank}. {item["source"]}

**Similarity:** `{item["score"]:.4f}`

{item["content"]}
"""
            )

        context = "\n\n".join(
            (
                f"[Source {index_number}: "
                f"{item['source']}]\n"
                f"{item['content']}"
            )
            for index_number, item
            in enumerate(
                retrieved,
                start=1,
            )
        )

        sources_markdown = "\n".join(
            source_blocks
        )

        return (
            context,
            sources_markdown,
        )

    except Exception as exc:
        error = (
            f"Retrieval error: "
            f"{type(exc).__name__}: {exc}"
        )

        return "", error


# =========================================================
# GENERATION
# Cloud adaptation:
# original local app uses Qwen 2.5 through Ollama.
# Demo uses hosted Qwen inference.
# =========================================================

def generate_answer(
    question,
    context,
):
    question = (question or "").strip()
    context = (context or "").strip()

    if not question:
        return "Please enter a question."

    if not context:
        return (
            "I could not retrieve enough "
            "evidence from the document."
        )

    token = os.environ.get(
        "HF_TOKEN"
    )

    if not token:
        return (
            "HF_TOKEN is not configured."
        )

    try:
        client = InferenceClient(
            provider="auto",
            api_key=token,
        )

        completion = (
            client.chat.completions.create(
                model=GENERATION_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a study assistant. "
                            "Answer ONLY using the provided "
                            "document context. "
                            "Do not use outside knowledge. "
                            "If the document does not contain "
                            "enough information, say that the "
                            "information was not found in the "
                            "document. "
                            "Keep the answer concise and clear. "
                            "Mention relevant page labels."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Document context:\n\n"
                            f"{context}\n\n"
                            f"Question:\n"
                            f"{question}"
                        ),
                    },
                ],
                temperature=0.2,
                max_tokens=300,
            )
        )

        answer = (
            completion
            .choices[0]
            .message
            .content
        )

        if not answer:
            return (
                "The generation model "
                "returned an empty response."
            )

        return answer

    except Exception as exc:
        return (
            "Generation error:\n\n"
            f"`{type(exc).__name__}: "
            f"{str(exc)}`"
        )


# =========================================================
# UI
# =========================================================

with gr.Blocks(
    title="Smart Study Assistant Demo"
) as demo:

    gr.Markdown(
        """
# Smart Study Assistant — Live RAG Demo

Ask questions about a real sample PDF.

### Live pipeline

**PDF → text extraction → 500/75 chunking → BGE-M3 → FAISS → Qwen → answer + page sources**

This is a cloud demo adaptation of the original local Smart Study Assistant.
"""
    )

    gr.Markdown(
        """
**Sample material:** Machine Learning Notes  
**Document type:** PDF  
**Retrieval:** BGE-M3 + FAISS IndexFlatIP
"""
    )

    question = gr.Textbox(
        label="Ask the sample PDF",
        placeholder=(
            "Example: What is overfitting?"
        ),
    )

    ask_button = gr.Button(
        "Ask the Document",
        variant="primary",
    )

    gr.Markdown("## Answer")

    answer_output = gr.Markdown()

    gr.Markdown(
        "## Retrieved Sources"
    )

    sources_output = gr.Markdown()

    context_state = gr.State("")

    gr.Examples(
        examples=[
            [
                "What is overfitting?"
            ],
            [
                "How does regularization "
                "help reduce overfitting?"
            ],
            [
                "Explain the bias-variance "
                "tradeoff."
            ],
        ],
        inputs=question,
    )

    retrieval_event = (
        ask_button.click(
            fn=retrieve_context,
            inputs=question,
            outputs=[
                context_state,
                sources_output,
            ],
            api_name="retrieve",
        )
    )

    retrieval_event.then(
        fn=generate_answer,
        inputs=[
            question,
            context_state,
        ],
        outputs=answer_output,
        api_name="generate",
    )


if __name__ == "__main__":
    demo.launch()