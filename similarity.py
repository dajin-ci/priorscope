"""
similarity.py

M·P 핵심 기술 요소를 텍스트 임베딩해서 코드로 유사도를 계산한다. (멘토링 10/27 #4·#5)

- LLM 판정을 대체하지 않는다. validator가 "없음" 판정을 교차 검증하는 보조 지표로만 쓴다.
  ("의미 판단은 에이전트, 숫자 계산은 코드", "검증은 강등만 한다" 원칙 유지)
- Upstage Embeddings API (OpenAI 호환, base_url은 v1. 에이전트 API의 v2와 다름)
- 같은 텍스트는 다시 보내지 않도록 캐시한다. 캐시에는 텍스트 원문이 아니라 해시와 벡터만 남는다.

사용법 (프로젝트 폴더에서):
    python similarity.py
    python similarity.py output/my_paper.json output/prior_paper.json result/similarity.json
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Callable, Sequence

from ids import SECTION_PATTERN, assign_ids

BASE_DIR = Path(__file__).resolve().parent

EMBED_BASE_URL = "https://api.upstage.ai/v1"
# 두 요소를 대칭으로 비교하므로 양쪽 모두 passage 모델을 쓴다.
EMBED_MODEL = os.getenv("EMBED_MODEL", "embedding-passage")
BATCH_SIZE = 100  # Upstage 한 번 요청 최대 개수
TOP_K = 3

DEFAULT_MY = BASE_DIR / "output" / "my_paper.json"
DEFAULT_PRIOR = BASE_DIR / "output" / "prior_paper.json"
DEFAULT_OUT = BASE_DIR / "result" / "similarity.json"
DEFAULT_CACHE = BASE_DIR / "result" / "embedding_cache.json"

Embedder = Callable[[Sequence[str]], list[list[float]]]


##################################################
# 텍스트 준비
##################################################

def element_text(text: str) -> str:
    """'[3.1] 원문 표현 | 한국어 설명'에서 섹션 태그만 떼고 원문과 설명을 함께 쓴다.
    섹션 번호는 의미와 무관하고, 한국어 설명이 있어야 국문·영문 논문끼리도 비교된다."""
    return SECTION_PATTERN.sub("", str(text), count=1).strip()


##################################################
# 임베딩
##################################################

class UpstageEmbedder:
    """Upstage 임베딩 호출 + 해시 캐시."""

    def __init__(self, model: str = EMBED_MODEL, cache_path: Path | None = DEFAULT_CACHE):
        self.model = model
        self.cache_path = Path(cache_path) if cache_path else None
        self._cache = self._load_cache()
        self._client = None

    def _load_cache(self) -> dict[str, list[float]]:
        if self.cache_path and self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {}
        return {}

    def _save_cache(self) -> None:
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache), encoding="utf-8")

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model}\n{text}".encode("utf-8")).hexdigest()

    def _call(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            from openai import OpenAI

            api_key = os.getenv("UPSTAGE_API_KEY")
            if not api_key:
                from dotenv import load_dotenv

                load_dotenv()
                api_key = os.getenv("UPSTAGE_API_KEY")
            self._client = OpenAI(api_key=api_key, base_url=EMBED_BASE_URL)
        response = self._client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        missing = [t for t in dict.fromkeys(texts) if self._key(t) not in self._cache]
        for start in range(0, len(missing), BATCH_SIZE):
            batch = missing[start:start + BATCH_SIZE]
            for text, vector in zip(batch, self._call(batch)):
                self._cache[self._key(text)] = vector
        if missing:
            self._save_cache()
        return [self._cache[self._key(t)] for t in texts]


##################################################
# 유사도
##################################################

def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def compute_similarity(my_paper: dict, prior_paper: dict, embedder: Embedder,
                       model: str = EMBED_MODEL, top_k: int = TOP_K) -> dict:
    """M×P 코사인 유사도 행렬과 M별 상위 P를 계산한다. 번호는 ids.assign_ids()와 같다."""
    ids = assign_ids(my_paper, prior_paper)
    m_items, p_items = ids["M"], ids["P"]
    if not m_items or not p_items:
        return {"model": model, "m_ids": [m["id"] for m in m_items], "p_ids": [p["id"] for p in p_items],
                "matrix": {}, "per_m": [], "stats": None}

    vectors = embedder([element_text(x["text"]) for x in m_items + p_items])
    m_vecs, p_vecs = vectors[:len(m_items)], vectors[len(m_items):]

    matrix: dict[str, dict[str, float]] = {}
    per_m = []
    all_scores = []
    for m, mv in zip(m_items, m_vecs):
        row = {p["id"]: round(cosine(mv, pv), 4) for p, pv in zip(p_items, p_vecs)}
        matrix[m["id"]] = row
        ranked = sorted(row.items(), key=lambda kv: kv[1], reverse=True)
        per_m.append({
            "id": m["id"],
            "max_score": ranked[0][1],
            "best_p": ranked[0][0],
            "top": [{"id": pid, "score": score} for pid, score in ranked[:top_k]],
        })
        all_scores.extend(row.values())

    return {
        "model": model,
        "m_ids": [m["id"] for m in m_items],
        "p_ids": [p["id"] for p in p_items],
        "matrix": matrix,
        "per_m": per_m,
        "stats": {
            "min": min(all_scores),
            "max": max(all_scores),
            "mean": round(sum(all_scores) / len(all_scores), 4),
        },
    }


##################################################
# CLI
##################################################

def main(argv: list[str]) -> None:
    if len(argv) not in (1, 4):
        print("사용법: python similarity.py [my_paper.json prior_paper.json out.json]")
        sys.exit(1)
    my_path, prior_path, out_path = (Path(a) for a in argv[1:]) if len(argv) == 4 else (DEFAULT_MY, DEFAULT_PRIOR, DEFAULT_OUT)

    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    result = compute_similarity(load(my_path), load(prior_path), UpstageEmbedder())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"모델 {result['model']} | M {len(result['m_ids'])}개 × P {len(result['p_ids'])}개")
    if result["stats"]:
        print(f"전체 유사도 범위 {result['stats']['min']} ~ {result['stats']['max']} (평균 {result['stats']['mean']})")
        for row in result["per_m"]:
            tops = ", ".join(f"{t['id']} {t['score']:.3f}" for t in row["top"])
            print(f"  {row['id']}: {tops}")
    print(f"저장 완료: {out_path}")


if __name__ == "__main__":
    main(sys.argv)
