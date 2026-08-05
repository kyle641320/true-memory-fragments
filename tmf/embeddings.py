from __future__ import annotations

import json
import math
import os
import shlex
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddedItem:
    index: int
    score: float


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def embed_texts(texts_untrusted_data: list[str]) -> list[list[float]] | None:
    command = os.environ.get("TMF_EMBED_COMMAND")
    if not command:
        return None
    payload = {"texts_untrusted_data": texts_untrusted_data}
    try:
        proc = subprocess.run(
            shlex.split(command),
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=True,
        )
        data = json.loads(proc.stdout)
    except Exception:
        return None
    vectors = data.get("vectors") if isinstance(data, dict) else None
    if not isinstance(vectors, list) or len(vectors) != len(texts_untrusted_data):
        return None
    out: list[list[float]] = []
    for vector in vectors:
        if not isinstance(vector, list):
            return None
        try:
            out.append([float(x) for x in vector])
        except Exception:
            return None
    return out


def rank_by_embedding(query_untrusted_data: str, texts_untrusted_data: list[str], limit: int) -> list[EmbeddedItem]:
    vectors = embed_texts([query_untrusted_data, *texts_untrusted_data])
    if vectors is None or len(vectors) < 2:
        return []
    query_vector = vectors[0]
    ranked = [EmbeddedItem(index=i, score=_cosine(query_vector, vector)) for i, vector in enumerate(vectors[1:])]
    ranked = [item for item in ranked if item.score > 0]
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:limit]
