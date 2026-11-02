"""Compare Agent 반복 실행 판정 합치기 (2026-11-02 확정 규칙)."""
import pytest

from validator import consensus_verdict


# v8-rules 세 번 실행에서 실제로 나온 판정 조합
@pytest.mark.parametrize("votes,expected", [
    (["없음", "없음", "없음"], "없음"),
    (["일치", "일치", "일치"], "일치"),
    (["유사", "없음", "유사"], "유사"),          # S1 M5: 과반이 겹침이면 그대로
    (["유사", "없음", "없음"], "확인필요"),      # S1 M6·M8: 겹침을 본 실행이 있으면 없음으로 단정하지 않음
    (["유사", "확인필요", "없음"], "확인필요"),  # S1 M7: 과반 없음
    (["없음", "유사", "유사"], "유사"),          # S2 M2
    (["일치", "유사", "없음"], "확인필요"),
    (["없음", "없음", "확인필요"], "없음"),
])
def test_consensus_rule(votes, expected):
    assert consensus_verdict(votes)[0] == expected


def test_single_run_is_unchanged():
    assert consensus_verdict(["없음"]) == ("없음", None)


def test_never_creates_overlap_from_nothing():
    for votes in (["없음", "없음", "확인필요"], ["없음", "확인필요", "확인필요"]):
        assert consensus_verdict(votes)[0] in ("없음", "확인필요")


def test_reason_is_given_when_demoted():
    verdict, reason = consensus_verdict(["유사", "없음", "없음"])
    assert verdict == "확인필요" and "유사 / 없음 / 없음" in reason


def test_combine_runs_picks_representative_and_recomputes_grade(monkeypatch):
    import validator

    def fake_run(final):
        rows = [{"id": f"M{i}", "text": "", "section": None, "prior_ids": [], "agent_verdict": v,
                 "final_verdict": v, "evidence": f"run-{final}", "explanation": "", "demoted_reasons": []}
                for i, v in enumerate(final, start=1)]
        return {"status": "PASSED", "mappings": rows, "numeric_checks": []}

    runs = iter([fake_run(["유사", "없음", "없음", "없음"]),
                 fake_run(["유사", "유사", "없음", "없음"]),
                 fake_run(["유사", "없음", "없음", "없음"])])
    monkeypatch.setattr(validator, "validate", lambda *a, **k: next(runs))
    monkeypatch.setattr(validator, "derive_weaknesses", lambda *a: {})
    out = validator.combine_runs({}, {}, [{"overlap_level": ["Low Overlap"]}] * 3)
    # M2 는 유사/없음/없음 → 확인필요
    assert [m["final_verdict"] for m in out["mappings"]] == ["유사", "확인필요", "없음", "없음"]
    assert out["mappings"][1]["votes"] == ["없음", "유사", "없음"]
    assert out["consensus"]["representative_run"] == 1 and out["consensus"]["agreement_rate"] == 0.75
    assert out["coverage"]["min"] == 12.5 and out["coverage"]["max"] == 37.5
    assert out["final_level"] == "판정 보류" and out["status"] == "NEEDS_REVIEW"
