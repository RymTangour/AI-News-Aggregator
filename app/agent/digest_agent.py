import os
import re
import json
import uuid
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
import ollama
import chromadb
from chromadb.config import Settings

load_dotenv()

# ── Models ────────────────────────────────────────────────────────────────────

class QAItem(BaseModel):
    question: str
    answer: str

class DigestOutput(BaseModel):
    title: str
    summary: str
    qa_pairs: list[QAItem]

# ── Config ────────────────────────────────────────────────────────────────────

EMBED_MODEL  = "nomic-embed-text"   # ollama pull nomic-embed-text
CHAT_MODEL   = "llama3.1:latest"
CHUNK_SIZE   = 512                  # characters per chunk
CHUNK_OVERLAP = 64                  # overlap between chunks
TOP_K        = 5                    # chunks retrieved per question
NUM_QUESTIONS = 10

CHROMA_DIR   = "./chroma_db"

# ── ChromaDB client (persistent, local) ───────────────────────────────────────

_client = chromadb.PersistentClient(
    path=CHROMA_DIR,
    settings=Settings(anonymized_telemetry=False)
)
_collection = _client.get_or_create_collection(
    name="articles",
    metadata={"hnsw:space": "cosine"}
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return [c for c in chunks if c]


def _embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts using Ollama."""
    embeddings = []
    for text in texts:
        response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
        embeddings.append(response["embedding"])
    return embeddings


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in: {text[:200]}")
    return json.loads(match.group())


def _extract_json_list(text: str) -> list:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in: {text[:200]}")
    return json.loads(match.group())


# ── Core pipeline ─────────────────────────────────────────────────────────────

def ingest_article(article_id: str, title: str, content: str, category: str) -> int:
    """
    Chunk the article, embed each chunk, and store in ChromaDB.
    Returns the number of chunks stored.
    """
    chunks = _chunk_text(content)
    embeddings = _embed(chunks)

    ids        = [f"{article_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas  = [{"article_id": article_id, "title": title, "category": category, "chunk_index": i}
                  for i in range(len(chunks))]

    _collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    return len(chunks)


def retrieve_chunks(question: str, article_id: str, top_k: int = TOP_K) -> list[str]:
    """
    Embed the question and retrieve the top_k most relevant chunks
    for the given article from ChromaDB.
    """
    q_embedding = _embed([question])[0]
    results = _collection.query(
        query_embeddings=[q_embedding],
        n_results=top_k,
        where={"article_id": article_id},
    )
    return results["documents"][0] if results["documents"] else []


def generate_questions(title: str, category: str) -> list[str]:
    """Ask the LLM to generate NUM_QUESTIONS questions about this article."""
    prompt = f"""You are an expert AI analyst.
Given an article titled "{title}" in the category "{category}", generate exactly {NUM_QUESTIONS} insightful questions a reader would want answered after reading it.

Return ONLY a JSON array of strings, no extra text:
["question 1", "question 2", ...]
"""
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response["message"]["content"]
    return _extract_json_list(raw)


def answer_question(question: str, context_chunks: list[str]) -> str:
    """Answer a single question using retrieved context chunks."""
    context = "\n\n---\n\n".join(context_chunks)
    prompt = f"""You are an expert AI analyst. Answer the question using ONLY the context provided below.
Be concise (2-4 sentences). If the context doesn't contain enough information, say so.

Context:
{context}

Question: {question}

Answer:"""
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"].strip()


def generate_summary(title: str, qa_pairs: list[QAItem]) -> str:
    """Generate a 2-3 sentence summary from the Q&A pairs."""
    qa_text = "\n".join([f"Q: {qa.question}\nA: {qa.answer}" for qa in qa_pairs[:5]])
    prompt = f"""Based on the following Q&A about "{title}", write a 2-3 sentence summary of the article's key insights.
Be concise and focus on what matters most.

{qa_text}

Summary:"""
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    return response["message"]["content"].strip()


# ── Main agent class ──────────────────────────────────────────────────────────

class DigestAgent:
    def generate_digest(
        self,
        title: str,
        content: str,
        article_type: str,
        article_id: Optional[str] = None,
    ) -> Optional[DigestOutput]:
        """
        Full RAG pipeline:
        1. Chunk + embed + store article in ChromaDB
        2. LLM generates 10 questions from title + category
        3. RAG retrieves relevant chunks per question
        4. LLM answers each question from retrieved chunks
        5. LLM summarizes the Q&A into a digest
        """
        try:
            if article_id is None:
                article_id = str(uuid.uuid4())

            # Step 1 — Ingest
            n_chunks = ingest_article(
                article_id=article_id,
                title=title,
                content=content,
                category=article_type,
            )
            print(f"[RAG] Ingested '{title}' → {n_chunks} chunks stored")

            # Step 2 — Generate questions
            questions = generate_questions(title=title, category=article_type)
            print(f"[RAG] Generated {len(questions)} questions")

            # Step 3 & 4 — Retrieve + Answer
            qa_pairs = []
            for i, question in enumerate(questions[:NUM_QUESTIONS]):
                chunks  = retrieve_chunks(question=question, article_id=article_id)
                answer  = answer_question(question=question, context_chunks=chunks)
                qa_pairs.append(QAItem(question=question, answer=answer))
                print(f"[RAG] Q{i+1} answered")

            # Step 5 — Summarize
            summary = generate_summary(title=title, qa_pairs=qa_pairs)

            return DigestOutput(
                title=title,
                summary=summary,
                qa_pairs=qa_pairs,
            )

        except Exception as e:
            print(f"[DigestAgent] Error: {e}")
            return None