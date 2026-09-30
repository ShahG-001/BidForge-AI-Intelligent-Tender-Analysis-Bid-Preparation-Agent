"""Small BM25-style lexical retriever for uploaded company evidence.

V1 keeps chunks in Streamlit session memory. No embedding API, local model,
vector database, or durable company document storage is required.
"""
import math
import re
from collections import Counter


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+#/-]*", re.IGNORECASE)
STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "will", "shall", "must",
    "are", "was", "were", "has", "have", "had", "into", "under", "over", "than",
    "their", "there", "which", "when", "where", "what", "who", "how", "your",
    "our", "you", "they", "them", "its", "not", "all", "any", "can", "may",
}


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text) if token.lower() not in STOPWORDS and len(token) > 1]


def chunk_source(text: str, filename: str, max_chars: int = 1200) -> list[dict]:
    """Turn extracted text into source-labelled paragraphs of bounded size."""
    sections, active_source, buffer = [], filename, ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if buffer:
                sections.append((active_source, buffer.strip()))
                buffer = ""
            continue
        if line.startswith("[SOURCE:"):
            if buffer:
                sections.append((active_source, buffer.strip()))
                buffer = ""
            active_source = line.strip("[]")
            continue
        if len(buffer) + len(line) + 1 > max_chars and buffer:
            sections.append((active_source, buffer.strip()))
            buffer = ""
        buffer += ("\n" if buffer else "") + line
    if buffer:
        sections.append((active_source, buffer.strip()))

    chunks = []
    for source, body in sections:
        if len(body) <= max_chars:
            chunks.append({"source": source, "text": body, "tokens": tokenize(body)})
        else:
            for offset in range(0, len(body), max_chars):
                part = body[offset:offset + max_chars]
                chunks.append({"source": source, "text": part, "tokens": tokenize(part)})
    return chunks


def retrieve(query: str, chunks: list[dict], top_k: int = 4) -> list[dict]:
    """Return the top BM25-ranked company evidence chunks for a requirement."""
    query_terms = set(tokenize(query))
    if not query_terms or not chunks:
        return []
    docs = [chunk.get("tokens") or tokenize(chunk.get("text", "")) for chunk in chunks]
    doc_freq = Counter(term for terms in docs for term in set(terms))
    average_length = sum(len(terms) for terms in docs) / max(len(docs), 1)
    k1, b = 1.5, 0.75
    ranked = []
    total_docs = len(docs)
    for chunk, terms in zip(chunks, docs):
        frequencies = Counter(terms)
        score = 0.0
        length = len(terms)
        for term in query_terms:
            freq = frequencies.get(term, 0)
            if not freq:
                continue
            inverse_frequency = math.log(1 + (total_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += inverse_frequency * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * length / max(average_length, 1)))
        if score > 0:
            ranked.append({**chunk, "score": round(score, 4)})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:top_k]


def retrieve_for_requirements(requirements: list[dict], chunks: list[dict], top_k: int = 2) -> list[dict]:
    """Match every tender requirement to the most relevant submitted evidence."""
    matched = []
    for requirement in requirements:
        evidence = retrieve(requirement["requirement"], chunks, top_k=top_k)
        # A weak keyword overlap is not treated as proof of compliance.
        strong = [item for item in evidence if item["score"] >= 0.35]
        matched.append({**requirement, "evidence": strong})
    return matched
