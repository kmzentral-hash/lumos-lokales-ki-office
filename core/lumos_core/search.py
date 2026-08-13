from __future__ import annotations

import re

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .documents import _connection

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=12)


class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None
    section: str
    excerpt: str
    score: float


class SearchResponse(BaseModel):
    query: str
    evidence_found: bool
    answer: str
    hits: list[SearchHit]
    count: int


def _tokens(query: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"[\wäöüÄÖÜß-]{2,}", query.lower())))[:12]


def _excerpt(content: str, tokens: list[str], length: int = 340) -> str:
    lowered = content.lower()
    positions = [lowered.find(token) for token in tokens if lowered.find(token) >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - 90)
    end = min(len(content), start + length)
    return f"{'…' if start else ''}{content[start:end].strip()}{'…' if end < len(content) else ''}"


@router.post("/api/v1/search", response_model=SearchResponse, name="search_documents")
async def search_documents(request: SearchRequest) -> SearchResponse:
    tokens = _tokens(request.query)
    if not tokens:
        return SearchResponse(
            query=request.query,
            evidence_found=False,
            answer="Keine Fundstelle in fertig verarbeiteten Dokumenten gefunden.",
            hits=[],
            count=0,
        )

    clauses = " OR ".join("LOWER(c.content) LIKE ?" for _ in tokens)
    parameters = [f"%{token}%" for token in tokens]
    with _connection() as connection:
        rows = connection.execute(
            f"""SELECT c.id, c.content, c.page, c.section, c.chunk_index,
                       d.id AS document_id, d.name AS document_name
                FROM document_chunks c JOIN documents d ON d.id = c.document_id
                WHERE d.status = 'ready' AND ({clauses}) LIMIT 250""",
            parameters,
        ).fetchall()

    scored: list[tuple[float, object]] = []
    for row in rows:
        lowered = row["content"].lower()
        matched = sum(token in lowered for token in tokens)
        frequency = sum(min(lowered.count(token), 5) for token in tokens)
        scored.append((matched / len(tokens) * 10 + frequency * 0.25, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    hits = [
        SearchHit(
            chunk_id=row["id"], document_id=row["document_id"],
            document_name=row["document_name"], page=row["page"], section=row["section"],
            excerpt=_excerpt(row["content"], tokens), score=round(score, 2),
        )
        for score, row in scored[: request.limit]
    ]
    answer = (
        "Relevante Fundstellen aus deinen Dokumenten: "
        + " ".join(hit.excerpt for hit in hits[:3])
        if hits
        else "Keine Fundstelle in fertig verarbeiteten Dokumenten gefunden."
    )
    return SearchResponse(
        query=request.query, evidence_found=bool(hits), answer=answer, hits=hits, count=len(hits)
    )
