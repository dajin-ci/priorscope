"""임베딩 유사도와 교차 검증 단위 테스트. Upstage API를 호출하지 않는다 (가짜 임베더 사용)."""

import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

import validator  # noqa: E402
from calibrate_similarity import auc, collect_points, recommend, sweep  # noqa: E402
from similarity import UpstageEmbedder, compute_similarity, element_text  # noqa: E402


def fake_embed(texts):
    """단어 주머니 벡터. 같은 단어가 많을수록 코사인 유사도가 높다."""
    vectors = []
    for text in texts:
        vec = [0.0] * 64
        for word in re.findall(r"\w+", text.lower()):
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


MY = {"core_techniques": [
    "[1] new benchmark dataset for events | 새 데이터셋",
    "[3.2] shared embedding space alignment of audio and text | 공통 임베딩 공간 정렬",
], "experiment_results": []}
PRIOR = {"core_techniques": [
    "[3.2] shared embedding space alignment of image audio text | 공통 임베딩 공간 정렬",
    "[3.3] vision transformer encoder | 이미지 인코더",
], "experiment_results": []}
BASE_CMP = {
    "overlap_level": ["Low Overlap"], "llm_score": [10], "summary": ["s"], "related_work_draft": ["r"],
    "result_pairs": [], "caution_points": ["c"], "differentiation_suggestions": ["1", "2", "3"],
}
ALL_NONE = {**BASE_CMP, "element_mapping": [
    "M1 ↔ - | 없음 | 검토 범위 P1~P2 | x",
    "M2 ↔ - | 없음 | 검토 범위 P1~P2 | x",
]}


def test_element_text_drops_section_tag_only():
    assert element_text("[3.1] Foo bar | 설명") == "Foo bar | 설명"
    assert element_text("no tag | 설명") == "no tag | 설명"


def test_similarity_matrix_shape_and_ranking():
    sim = compute_similarity(MY, PRIOR, fake_embed, model="fake")
    assert sim["m_ids"] == ["M1", "M2"] and sim["p_ids"] == ["P1", "P2"]
    m2 = next(r for r in sim["per_m"] if r["id"] == "M2")
    assert m2["best_p"] == "P1"
    assert m2["max_score"] > sim["matrix"]["M1"]["P1"]


def test_no_threshold_reports_only():
    sim = compute_similarity(MY, PRIOR, fake_embed, model="fake")
    out = validator.validate(MY, PRIOR, ALL_NONE, similarity=sim, demote_threshold=None)
    assert [m["final_verdict"] for m in out["mappings"]] == ["없음", "없음"]
    assert out["similarity"]["available"] and out["similarity"]["demoted"] == []
    assert "similarity" in out["mappings"][1]


def test_high_similarity_demotes_none_to_review():
    sim = compute_similarity(MY, PRIOR, fake_embed, model="fake")
    threshold = (sim["matrix"]["M2"]["P1"] + sim["matrix"]["M1"]["P1"]) / 2
    out = validator.validate(MY, PRIOR, ALL_NONE, similarity=sim, demote_threshold=threshold)
    verdicts = {m["id"]: m["final_verdict"] for m in out["mappings"]}
    assert verdicts == {"M1": "없음", "M2": "확인필요"}
    assert out["similarity"]["demoted"] == ["M2"]
    assert out["status"] == "NEEDS_REVIEW"
    assert out["coverage"]["max"] > out["coverage"]["min"]  # 확인필요가 범위를 연다


def test_similarity_never_promotes():
    sim = compute_similarity(MY, PRIOR, fake_embed, model="fake")
    cmp_ = {**BASE_CMP, "element_mapping": [
        "M1 ↔ - | 없음 | 검토 범위 P1~P2 | x",
        "M2 ↔ P1 | 유사 | M[3.2] / P[3.2] | x",
    ]}
    out = validator.validate(MY, PRIOR, cmp_, similarity=sim, demote_threshold=0.0)
    verdicts = {m["id"]: m["final_verdict"] for m in out["mappings"]}
    assert verdicts["M2"] == "유사"  # 유사는 그대로 (승격도 강등도 안 함)
    assert verdicts["M1"] == "확인필요"


def test_mismatched_similarity_is_ignored():
    sim = compute_similarity(MY, PRIOR, fake_embed, model="fake")
    sim["p_ids"] = ["P1", "P2", "P3"]
    out = validator.validate(MY, PRIOR, ALL_NONE, similarity=sim, demote_threshold=0.0)
    assert not out["similarity"]["available"]
    assert all(m["final_verdict"] == "없음" for m in out["mappings"])


def test_embedder_cache_avoids_repeat_calls(tmp_path):
    calls = []

    class Counting(UpstageEmbedder):
        def _call(self, texts):
            calls.append(list(texts))
            return fake_embed(texts)

    emb = Counting(model="fake", cache_path=tmp_path / "cache.json")
    emb(["a b", "c d"])
    emb(["a b", "c d", "e f"])
    assert calls == [["a b", "c d"], ["e f"]]
    cache = json.loads((tmp_path / "cache.json").read_text())
    assert all(len(k) == 64 for k in cache)  # 텍스트 원문이 아니라 해시만 저장


def test_calibration_picks_threshold_under_false_alarm_budget(tmp_path):
    sample = tmp_path / "S1"
    sample.mkdir()
    (sample / "similarity.json").write_text(json.dumps({"per_m": [
        {"id": "M1", "max_score": 0.90}, {"id": "M2", "max_score": 0.80},
        {"id": "M3", "max_score": 0.60}, {"id": "M4", "max_score": 0.40},
        {"id": "M5", "max_score": 0.70},
    ]}))
    (sample / "labels.json").write_text(json.dumps({
        "M1": "일치", "M2": {"verdict": "유사", "prior": ["P1"]},
        "M3": "없음", "M4": "없음", "M5": "확인필요",
    }, ensure_ascii=False))
    points = collect_points(tmp_path)
    assert len(points) == 4  # 확인필요 정답은 제외
    assert auc(points) == 1.0
    best = recommend(sweep(points), max_false_alarm=0.0)
    assert best["recall"] == 1.0 and best["false_alarm"] == 0.0
    assert 0.60 < best["threshold"] <= 0.80
