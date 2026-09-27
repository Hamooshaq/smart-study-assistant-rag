---
title: Smart Study Assistant Demo
emoji: 📚
colorFrom: blue
colorTo: blue
sdk: gradio
sdk_version: 6.28.0
app_file: app.py
pinned: false
license: mit
suggested_hardware: zero-a10g
---

# Smart Study Assistant — Cloud Adapter

This Space is the temporary, public-demo adapter for the full local FastAPI application in the source repository. It exposes an explicit document-ID contract for browser and `@gradio/client` consumers:

- `/prepare_document`: upload PDF/PPTX once and build normalized BGE-M3 embeddings plus a FAISS `IndexFlatIP` index.
- `/ask_document`: reuse the prepared index for grounded multi-question chat with page/slide evidence.
- `/summarize_document`, `/generate_flashcards`, `/generate_quiz`, `/grade_quiz`: real document-grounded study tools.
- `/delete_document`: remove an ephemeral document session early.

Documents expire after 45 minutes of inactivity and are lost whenever the Space restarts. The cloud demo deliberately does not imitate the local app's accounts, durable SQLite history, activity/progress records, or optional vision pipeline.

The original application uses local Qwen 2.5 through Ollama. This Space uses hosted `Qwen/Qwen3-4B-Instruct-2507` for generation, while preserving the original BAAI/bge-m3, normalization, FAISS inner-product retrieval, 500-word chunks, 75-word overlap, and page/slide provenance.
