# Smart Study Assistant — Local RAG Application

A functional local Retrieval-Augmented Generation (RAG) study assistant for learning from PDF and PowerPoint documents.

Smart Study Assistant is a full-stack AI application designed to help users interact with their own learning materials through document-grounded question answering, summaries, flashcards, quizzes, and learning progress tracking.

The system runs locally using open-source models and does not rely on hosted LLM APIs.

---

## Overview

Smart Study Assistant allows users to:

- Register, log in, and log out
- Upload PDF, PPT, and PPTX learning materials
- Ask questions grounded in uploaded documents
- View page- and slide-level source references
- Generate summaries
- Generate flashcards
- Generate multiple-choice quizzes
- Submit quizzes and receive automatic scores
- Track learning progress
- Access previously generated study materials
- Keep documents and retrieval indexes separated per user
- Optionally process embedded document images using a local vision-language model

The project focuses on local AI inference, document-grounded generation, and end-to-end RAG application development.

---

## Architecture

```text
Browser UI
   │
   ├── Authentication
   ├── Document Upload
   ├── Document Chat
   ├── Summary Generation
   ├── Flashcards
   ├── Quiz
   └── Learning Progress
   │
   ▼
FastAPI Backend
   │
   ├── File Validation
   ├── PDF / PowerPoint Parsing
   ├── Page / Slide Provenance
   ├── Text Chunking
   ├── BGE-M3 Embeddings
   ├── FAISS Retrieval
   ├── Qwen 2.5 via Ollama
   └── SQLite Persistence
```

The application uses a local monolithic architecture.

The frontend is served alongside the FastAPI backend. Application data is stored in SQLite, while FAISS indexes are stored locally per document.

---

## Tech Stack

### Backend

- Python
- FastAPI
- Uvicorn
- SQLite

### Retrieval-Augmented Generation

- Sentence Transformers
- `BAAI/bge-m3`
- FAISS CPU
- `faiss.IndexFlatIP`
- Qwen 2.5 Instruct via Ollama

### Document Processing

- `pdfplumber`
- `python-pptx`
- PyMuPDF / `fitz`

### Frontend

- HTML
- CSS
- Vanilla JavaScript

### Optional Vision Pipeline

- LLaVA via Ollama
- PDF image extraction
- PowerPoint image extraction
- Visual-description indexing

### Testing

- Pytest

---

## RAG Pipeline

The main document-question-answering pipeline works as follows:

```text
PDF / PowerPoint
        │
        ▼
Document Parsing
        │
        ▼
Page / Slide Provenance
        │
        ▼
Overlapping Text Chunking
        │
        ▼
BGE-M3 Embeddings
        │
        ▼
FAISS Index
        │
        ▼
Question Embedding
        │
        ▼
Top-K Retrieval
        │
        ▼
Context Construction
        │
        ▼
Qwen 2.5 Generation
        │
        ▼
Answer + Source References
```

Default retrieval configuration:

```text
Chunk size        : 500
Chunk overlap     : 75
Top-K retrieval   : 5
Embedding model   : BAAI/bge-m3
Generator         : qwen2.5:7b-instruct
```

Embeddings are normalized before being stored in FAISS `IndexFlatIP`, so the inner-product ranking is equivalent to cosine-similarity ranking for normalized vectors.

---

## Features

### Authentication

The application implements local user authentication with:

- Registration
- Login
- Logout
- Password hashing
- Cookie-based sessions

Application resources are associated with individual users.

---

### Document Upload

Supported document formats:

- `.pdf`
- `.pptx`
- `.ppt`

PDF files are parsed with page-level provenance.

PowerPoint files are parsed with slide-level provenance.

Legacy `.ppt` conversion requires LibreOffice / `soffice` to be available locally.

---

### Document-Grounded Chat

Users can ask questions about their uploaded documents.

The application:

1. Embeds the user question using BGE-M3.
2. Retrieves relevant document chunks from FAISS.
3. Builds a context from the retrieved evidence.
4. Sends the context and question to Qwen 2.5 through Ollama.
5. Returns an answer together with source-location information.

Retrieved evidence preserves document provenance such as:

```text
Page 4
Slide 8
```

The generation prompt instructs the model to avoid inventing information when relevant evidence cannot be found in the supplied context.

---

### Summary Generation

Users can generate summaries from uploaded learning materials.

Generated summaries are persisted in SQLite for later access.

---

### Flashcards

The application can generate structured flashcards from uploaded document content.

Generated flashcards are persisted so users can review them later.

---

### Quiz Generation

The system can generate multiple-choice quizzes from document content.

The quiz workflow includes:

- Question generation
- Multiple-choice options
- Hidden answer keys
- Quiz submission
- Automatic grading
- Persisted quiz attempts

---

### Learning Progress

The application stores learning activity and provides lightweight progress information.

This includes:

- Recent learning activity
- Quiz results
- Study history
- Estimated learning progress
- Suggested next learning actions

---

## User Data Isolation

Application data is separated by user.

Persisted data can include:

- Users
- Sessions
- Documents
- Document chunks
- Chat history
- Summaries
- Flashcards
- Quizzes
- Quiz attempts
- Learning activity

SQLite is used for application persistence.

FAISS indexes are stored locally per document and associated with the relevant user's documents.

---

## Optional Vision-Language Pipeline

The project includes an optional vision-language processing module.

When enabled, images embedded in PDF and PowerPoint documents can be extracted and converted into textual descriptions using a local vision-language model.

The resulting descriptions can then be indexed alongside ordinary document text.

```text
Document Image
      │
      ▼
Image Extraction
      │
      ▼
LLaVA Captioning
      │
      ▼
Visual Description
      │
      ▼
Text Chunk
      │
      ▼
FAISS Index
```

The main text-based RAG pipeline continues to work when the vision module is disabled.

The vision pipeline is implemented as an optional module and should not be interpreted as a production-validated multimodal document-understanding system.

---

## Project Structure

```text
smart-study-assistant-rag/
├── backend/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── auth.py
│       ├── security.py
│       ├── database.py
│       ├── documents.py
│       ├── extraction.py
│       ├── chunking.py
│       ├── embedding.py
│       ├── vector_store.py
│       ├── rag.py
│       ├── ollama_client.py
│       ├── generation.py
│       ├── progress.py
│       ├── evaluation.py
│       └── vision.py
│
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
│
├── scripts/
│   └── evaluate_retrieval.py
│
├── tests/
│   ├── test_chunking.py
│   ├── test_evaluation.py
│   ├── test_file_validation.py
│   ├── test_quiz.py
│   ├── test_security.py
│   └── test_vision.py
│
├── docs/
│   └── black_box_testing.md
│
├── requirements.txt
├── pytest.ini
└── README.md
```

Local runtime data such as uploaded documents, SQLite databases, FAISS indexes, extracted images, and environment-specific files should not be committed to the public repository.

---

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Hamooshaq/smart-study-assistant-rag.git
cd smart-study-assistant-rag
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Install Ollama

Install Ollama and make sure the Ollama service is running.

Pull the default local language model:

```bash
ollama pull qwen2.5:7b-instruct
```

The default Ollama endpoint is:

```text
http://localhost:11434
```

---

## Run the Application

Start the FastAPI application:

```bash
uvicorn backend.app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

---

## Configuration

The application supports environment-based configuration.

Example:

```bash
export EMBEDDING_MODEL=BAAI/bge-m3
export OLLAMA_MODEL=qwen2.5:7b-instruct
export RAG_TOP_K=5
export CHUNK_SIZE=500
export CHUNK_OVERLAP=75
export MAX_UPLOAD_MB=50
```

Available configuration values include:

```text
APP_DB_PATH
UPLOAD_DIR
INDEX_DIR
VISION_DIR
SESSION_DAYS
MAX_UPLOAD_MB
EMBEDDING_MODEL
OLLAMA_URL
OLLAMA_MODEL
VLM_ENABLED
VLM_MODEL
VLM_MAX_IMAGES_PER_DOCUMENT
RAG_TOP_K
CHUNK_SIZE
CHUNK_OVERLAP
SUMMARY_MAX_CHARS
```

---

## Enable the Optional Vision Pipeline

Pull the default local vision-language model:

```bash
ollama pull llava:7b
```

Enable the vision module:

```bash
export VLM_ENABLED=true
export VLM_MODEL=llava:7b
```

Then run the application normally:

```bash
uvicorn backend.app.main:app --reload
```

---

## Testing

Run the unit tests with:

```bash
pytest
```

During the latest project inspection:

```text
12 passed
```

The current unit tests cover utilities including:

- Recursive chunk splitting
- PowerPoint slide provenance
- Visual chunk handling
- Hit@K
- Precision@K
- Mean Reciprocal Rank
- ROUGE-L
- File-extension validation
- Quiz answer-key hiding
- Quiz grading
- Password hashing
- Password verification

The project should not be interpreted as fully integration-tested.

Browser flows, live Ollama generation, live embedding inference, and end-to-end API workflows are not comprehensively covered by the current automated test suite.

---

## Evaluation Utilities

The project includes utilities for calculating:

- Hit@K
- Precision@K
- Mean Reciprocal Rank
- ROUGE-L

Example:

```bash
python scripts/evaluate_retrieval.py data/retrieval_results.jsonl
```

A completed evaluation dataset and final experimental benchmark are not retained in the current project artifacts.

For that reason, this repository does not claim measured retrieval accuracy, answer quality, or benchmark superiority.

---

## Project Status

**Status: Functional local prototype**

The project contains implemented flows for:

- Authentication
- Document ingestion
- Document parsing
- Chunking
- Embedding generation
- FAISS indexing
- Retrieval
- Local LLM generation
- Document-grounded chat
- Summaries
- Flashcards
- Quizzes
- Quiz grading
- Learning progress
- Application persistence

This project should be understood as an engineering prototype rather than:

- A production-ready platform
- A cloud-deployed application
- A validated educational intervention
- A completed retrieval benchmark
- A production security implementation

---

## Privacy and Repository Hygiene

Local runtime data should not be committed to GitHub.

The repository should exclude files such as:

```text
storage/app.db
storage/uploads/
storage/indexes/
storage/vision/
.env
.venv/
```

Uploaded user documents, user records, authentication sessions, local FAISS indexes, and other runtime artifacts should remain private.

For public demonstrations, use public-domain, openly licensed, or synthetic documents.

---

## Author

**Mohammad**

Computer Science  
Artificial Intelligence Specialization  
BINUS University

GitHub: https://github.com/Hamooshaq

LinkedIn: https://www.linkedin.com/in/mohammad-mohammad-96b035201/