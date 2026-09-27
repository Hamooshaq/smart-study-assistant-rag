import os
import re
import tempfile

from functools import lru_cache
from pathlib import Path

import faiss
import gradio as gr
import numpy as np
import pdfplumber
import spaces

from huggingface_hub import InferenceClient
from pptx import Presentation
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

def extract_uploaded_sections(file_path):
    if not file_path:
        raise ValueError("Please upload a document first.")

    path = Path(file_path)
    extension = path.suffix.lower()

    sections = []

    if extension == ".pdf":
        with pdfplumber.open(path) as pdf:
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
                            "slide_number": None,
                            "source_label": f"Page {page_number}",
                            "source_type": "pdf",
                        }
                    )

    elif extension == ".pptx":
        presentation = Presentation(str(path))

        for slide_number, slide in enumerate(
            presentation.slides,
            start=1,
        ):
            texts = []

            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    text = shape.text.strip()

                    if text:
                        texts.append(text)

            combined_text = "\n".join(texts).strip()

            if combined_text:
                sections.append(
                    {
                        "text": combined_text,
                        "page_number": None,
                        "slide_number": slide_number,
                        "source_label": f"Slide {slide_number}",
                        "source_type": "pptx",
                    }
                )

    else:
        raise ValueError(
            "Unsupported file type. Please upload a PDF or PPTX file."
        )

    if not sections:
        raise ValueError(
            "The uploaded document does not contain extractable text."
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

def build_uploaded_chunks(file_path):
    sections = extract_uploaded_sections(file_path)

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
                    "source_type": section["source_type"],
                    "page_number": section["page_number"],
                    "slide_number": section["slide_number"],
                    "content": part,
                }
            )

    if not chunks:
        raise ValueError(
            "No chunks were generated from the uploaded document."
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

@spaces.GPU
def prepare_uploaded_document(file_path):
    if not file_path:
        return None, "Please upload a PDF or PPTX file."

    try:
        chunks = build_uploaded_chunks(file_path)

        model = load_embedding_model()

        document_embeddings = model.encode(
            [chunk["content"] for chunk in chunks],
            batch_size=8,
            show_progress_bar=False,
        )

        document_embeddings = normalize(
            document_embeddings
        )

        prepared_document = {
            "chunks": chunks,
            "embeddings": document_embeddings,
            "filename": Path(file_path).name,
        }

        status = (
            f"Ready: **{Path(file_path).name}**  \n"
            f"Parsed and indexed **{len(chunks)} chunks**."
        )

        return prepared_document, status

    except Exception as exc:
        return (
            None,
            (
                f"Document preparation error: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

@spaces.GPU
def retrieve_prepared_document(question, prepared_document):
    question = (question or "").strip()

    if not question:
        return "", "Please enter a question."

    if not prepared_document:
        return "", "Please prepare a document first."

    try:
        chunks = prepared_document["chunks"]

        document_embeddings = np.asarray(
            prepared_document["embeddings"],
            dtype="float32",
        )

        model = load_embedding_model()

        query_embedding = model.encode(
            [question],
            show_progress_bar=False,
        )

        query_embedding = normalize(
            query_embedding
        )

        index = faiss.IndexFlatIP(
            document_embeddings.shape[1]
        )

        index.add(
            document_embeddings
        )

        scores, positions = index.search(
            query_embedding,
            min(TOP_K, len(chunks)),
        )

        retrieved = []

        for position, score in zip(
            positions[0],
            scores[0],
        ):
            if position < 0:
                continue

            chunk = chunks[int(position)]

            retrieved.append(
                {
                    "source": chunk["source"],
                    "content": chunk["content"],
                    "score": float(score),
                }
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

        source_blocks = []

        for rank, item in enumerate(
            retrieved,
            start=1,
        ):
            source_blocks.append(
                f"""
### {rank}. {item["source"]}

**Similarity:** `{item["score"]:.4f}`

{item["content"]}
"""
            )

        sources_markdown = "\n".join(
            source_blocks
        )

        return (
            context,
            sources_markdown,
        )

    except Exception as exc:
        return (
            "",
            (
                f"Retrieval error: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

def retrieve_from_chunks(question, chunks):
    question = (question or "").strip()

    if not question:
        raise ValueError("Please enter a question.")

    if not chunks:
        raise ValueError("No document chunks are available.")

    model = load_embedding_model()

    document_embeddings = model.encode(
        [chunk["content"] for chunk in chunks],
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
        min(TOP_K, len(chunks)),
    )

    retrieved = []

    for position, score in zip(
        positions[0],
        scores[0],
    ):
        if position < 0:
            continue

        chunk = chunks[int(position)]

        retrieved.append(
            {
                "source": chunk["source"],
                "content": chunk["content"],
                "score": float(score),
            }
        )

    return retrieved

# =========================================================
# RETRIEVAL
# Same pattern as original FAISS IndexFlatIP retrieval
# =========================================================

@spaces.GPU
def retrieve_context(question):
    question = (question or "").strip()

    if not question:
        return "", "Please enter a question."

    try:
        chunks = build_sample_chunks()

        retrieved = retrieve_from_chunks(
            question,
            chunks,
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

        source_blocks = []

        for rank, item in enumerate(
            retrieved,
            start=1,
        ):
            source_blocks.append(
                f"""
### {rank}. {item["source"]}

**Similarity:** `{item["score"]:.4f}`

{item["content"]}
"""
            )

        sources_markdown = "\n".join(
            source_blocks
        )

        return (
            context,
            sources_markdown,
        )

    except Exception as exc:
        return (
            "",
            (
                f"Retrieval error: "
                f"{type(exc).__name__}: {exc}"
            ),
        )

@spaces.GPU
def retrieve_uploaded_context(file_path, question):
    question = (question or "").strip()

    if not file_path:
        return "", "Please upload a PDF or PPTX file."

    if not question:
        return "", "Please enter a question."

    try:
        chunks = build_uploaded_chunks(file_path)

        retrieved = retrieve_from_chunks(
            question,
            chunks,
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

        source_blocks = []

        for rank, item in enumerate(
            retrieved,
            start=1,
        ):
            source_blocks.append(
                f"""
### {rank}. {item["source"]}

**Similarity:** `{item["score"]:.4f}`

{item["content"]}
"""
            )

        sources_markdown = "\n".join(
            source_blocks
        )

        return (
            context,
            sources_markdown,
        )

    except Exception as exc:
        return (
            "",
            (
                f"Retrieval error: "
                f"{type(exc).__name__}: {exc}"
            ),
        )
    
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

    gr.Markdown("---")

    gr.Markdown(
        """
## Upload Your Own Document

Upload a text-based PDF or PPTX and ask questions using the same
BGE-M3 + FAISS retrieval pipeline.
"""
    )

    uploaded_file = gr.File(
        label="Upload PDF or PPTX",
        file_types=[".pdf", ".pptx"],
        type="filepath",
    )

    prepare_button = gr.Button(
        "Prepare Document",
        variant="secondary",
    )

    prepare_status = gr.Markdown(
        "Upload a document, then prepare it before asking questions."
    )

    prepared_document_state = gr.State(None)

    uploaded_question = gr.Textbox(
        label="Ask your uploaded document",
        placeholder="Example: What is the main topic of this document?",
    )

    uploaded_ask_button = gr.Button(
        "Ask Uploaded Document",
        variant="secondary",
    )

    gr.Markdown("### Answer")

    uploaded_answer_output = gr.Markdown()

    gr.Markdown("### Retrieved Sources")

    uploaded_sources_output = gr.Markdown()

    uploaded_context_state = gr.State("")

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

    prepare_event = prepare_button.click(
        fn=prepare_uploaded_document,
        inputs=uploaded_file,
        outputs=[
            prepared_document_state,
            prepare_status,
        ],
        api_name="prepare_uploaded",
    )

    uploaded_retrieval_event = uploaded_ask_button.click(
        fn=retrieve_prepared_document,
        inputs=[
            uploaded_question,
            prepared_document_state,
        ],
        outputs=[
            uploaded_context_state,
            uploaded_sources_output,
        ],
        api_name="retrieve_uploaded",
    )

    uploaded_retrieval_event.then(
        fn=generate_answer,
        inputs=[
            uploaded_question,
            uploaded_context_state,
        ],
        outputs=uploaded_answer_output,
        api_name="generate_uploaded",
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