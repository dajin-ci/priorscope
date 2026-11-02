"""eval/evaluate.py 테스트 (Studio·Solar 호출 없음)."""
import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))

import evaluate  # noqa: E402


def suit(route, axes=None):
    return {"route": route, "comparison_allowed": route in evaluate.COMPARABLE,
            "axes": {k: {"relation": v} for k, v in (axes or {}).items()}}


def verified_from_labels(sample, flip=None, level="Medium Overlap"):
    """정답 라벨을 그대로 예측으로 만든다. flip={M번호: 최종판정} 으로 일부를 틀리게 한다."""
    labels = json.loads((ROOT / "eval" / "samples" / sample / "labels.json").read_text(encoding="utf-8"))
    flip = flip or {}
    rows = [{"id": m, "agent_verdict": flip.get(m, v["verdict"]), "final_verdict": flip.get(m, v["verdict"]),
             "demoted_reasons": []} for m, v in labels.items()]
    return {"mappings": rows, "final_level": level}


def test_perfect_prediction_on_s2():
    truth = evaluate.load_truth("S2")
    pred = {"suitability": suit("research", {"problem": "same", "scope": "comparable", "method": "specific_shared"}),
            "verified": verified_from_labels("S2")}
    s = evaluate.score_sample(truth, pred)
    assert s["route_correct"] and s["route_correct_vs_sheet"] and not s["gate_leak"]
    assert all(a["correct"] for a in s["axes"].values())
    assert s["grade"] == {"pred": "Medium Overlap", "truth": "Medium Overlap", "held": False, "correct": True}
    m = evaluate.aggregate([s])
    assert m["false_novelty_rate"] == 0 and m["element_accuracy"] == 1 and m["provisional"] is True


def test_false_novelty_counts_overlap_judged_none():
    truth = evaluate.load_truth("S2")
    # S2 정답의 유사 6개 중 M1, M4 를 '없음'으로 틀리게 예측
    pred = {"suitability": suit("research"), "verified": verified_from_labels("S2", {"M1": "없음", "M4": "없음"})}
    m = evaluate.aggregate([evaluate.score_sample(truth, pred)])
    assert m["false_novelty_rate"] == pytest.approx(2 / 6)
    assert m["element_accuracy"] == pytest.approx(7 / 9)
    assert evaluate.check_targets(m)["false_novelty_rate"] is False


def test_validator_effect_is_visible():
    truth = evaluate.load_truth("S2")
    verified = verified_from_labels("S2")
    verified["mappings"][0].update(agent_verdict="없음", final_verdict="확인필요")  # 검증이 강등해 막은 경우
    m = evaluate.aggregate([evaluate.score_sample(truth, {"suitability": suit("research"), "verified": verified})])
    assert m["false_novelty_rate_agent"] > m["false_novelty_rate"] == 0


def test_route_wrong_by_extraction_vs_judgment():
    truth = evaluate.load_truth("S1")  # 정답 partial
    s = evaluate.score_sample(truth, {"suitability": suit("method"), "verified": None})
    assert s["route_correct"] is False and s["over_block"] is False and s["elements"] is None


def test_designed_sample_leak_and_over_block():
    manifest = {"S5": {"label_mode": "designed", "acceptable_routes": ["insufficient", "unsuitable"]}}
    truth = evaluate.load_truth("S5", folder=Path("/nonexistent"), manifest=manifest)
    leak = evaluate.score_sample(truth, {"suitability": suit("method"), "verified": {}})
    assert leak["gate_leak"] and not leak["route_correct"]
    ok = evaluate.score_sample(truth, {"suitability": suit("unsuitable"), "verified": None})
    m = evaluate.aggregate([leak, ok])
    assert m["gate_leak_rate"] == 0.5
    s2 = evaluate.score_sample(evaluate.load_truth("S2"), {"suitability": suit("unsuitable"), "verified": None})
    assert s2["over_block"] and evaluate.aggregate([s2])["over_block_rate"] == 1


def test_held_grade_is_not_counted_as_agreement():
    truth = evaluate.load_truth("S2")
    s = evaluate.score_sample(truth, {"suitability": suit("research"), "verified": verified_from_labels("S2", level="판정 보류")})
    m = evaluate.aggregate([s])
    assert m["grade_agreement"] is None and m["grade_held"] == 1


def test_unlabeled_sample_has_no_truth(tmp_path):
    assert evaluate.load_truth("S9", folder=tmp_path, manifest={}) is None


def test_compare_runs_shared_service_path_and_scores(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "UPSTAGE_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(config, "validate_config", lambda: None)
    import service

    def fake_run(my, prior, out, on_step=None):
        sample = out.name
        route = {"S1": "partial", "S2": "research"}[sample]
        (out / "suitability.json").write_text(json.dumps(suit(route)), encoding="utf-8")
        (out / "validated_result.json").write_text(json.dumps(verified_from_labels(sample)), encoding="utf-8")
        return {}

    run = Mock(side_effect=fake_run)
    monkeypatch.setattr(service, "run_from_extracted", run)
    monkeypatch.setattr(evaluate, "RESULTS_DIR", tmp_path)
    report = evaluate.cmd_compare(["S1", "S2"], "t")
    assert run.call_count == 2
    assert report["metrics"]["route_accuracy"] == 1 and report["metrics"]["false_novelty_rate"] == 0
    assert (tmp_path / "t" / "report.json").exists() and (tmp_path / "t" / "S1" / "timing.json").exists()
    # 저장된 결과는 API 없이 다시 채점할 수 있다
    assert evaluate.score_dir(tmp_path / "t")["metrics"] == report["metrics"]


def test_stability_summary_flags_drift():
    runs = [{"n_m": 8, "n_p": 8, "route": "partial", "final_level": "적용 안 함", "seconds": 90},
            {"n_m": 8, "n_p": 4, "route": "method", "final_level": "적용 안 함", "seconds": 80}]
    s = evaluate.stability_summary(runs)
    assert s["p_count"] == {"values": [8, 4], "min": 4, "max": 8}
    assert s["route_consistent"] is False and s["level_consistent"] is True


def test_cli_usage_returns_error():
    assert evaluate.main([]) == 1 and evaluate.main(["score"]) == 1
