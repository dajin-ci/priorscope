"""적합성 N회 호출 합치기. 외부 API 호출 없음."""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from suitability import SYSTEM_PROMPT, assess_suitability, combine_assessments, normalize_assessment

PAPER = {
    "title": ["연구"],
    "problem": ["[1] 텍스트 분류의 정확도를 높인다."],
    "core_techniques": ["[3] 동적 마스킹을 적용한다."],
    "experiment_results": [],
}


def raw(problem="same", scope="comparable", method="specific_shared"):
    out = {}
    for axis, relation in (("problem", problem), ("scope", scope), ("method", method)):
        field = "core_techniques" if axis == "method" else "problem"
        ev = [{"field": field, "index": 0, "quote": PAPER[field][0]}]
        out[axis] = {"relation": relation, "reason": "근거", "my_evidence": deepcopy(ev), "prior_evidence": deepcopy(ev)}
    return out


def gate(**kw):
    return normalize_assessment(raw(**kw), PAPER, PAPER)


def response(content):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=json.dumps(content)))])


def test_unanimous_keeps_route_and_records_votes():
    out = combine_assessments([gate(), gate(), gate()])
    assert out["route"] == "research"
    assert out["consensus"]["unanimous"] is True
    assert out["axes"]["problem"]["votes"] == ["same", "same", "same"]


def test_split_between_research_and_partial_picks_partial_and_warns():
    # 2026-11-03 S2 stability: problem 축만 same/related 로 갈림
    out = combine_assessments([gate(problem="related"), gate(problem="related"), gate()])
    assert out["route"] == "partial"
    assert out["consensus"]["routes"] == ["partial", "partial", "research"]
    assert out["axes"]["problem"]["votes"] == ["related", "related", "same"]
    assert any("해결 문제" in w and "보수적" in w for w in out["warnings"])


def test_minority_conservative_route_still_wins():
    out = combine_assessments([gate(), gate(), gate(problem="related")])
    assert out["route"] == "partial"


def test_split_between_allowed_and_blocked_is_deferred():
    out = combine_assessments([gate(), gate(problem="different", scope="different", method="generic_only")])
    assert out["route"] == "insufficient"
    assert out["comparison_allowed"] is False


def test_failed_run_is_ignored_when_others_succeed():
    failed = gate()
    failed = combine_assessments([failed])  # 형식 맞추기용 복사
    failed = dict(failed, route="insufficient", comparison_allowed=False, error_type="Timeout")
    out = combine_assessments([gate(), failed, gate()])
    assert out["route"] == "research"
    assert out["consensus"]["failed_runs"] == 1


def test_runs_parameter_controls_call_count():
    client = Mock()
    client.chat.completions.create.return_value = response(raw())
    assert assess_suitability(PAPER, PAPER, client=client, runs=1)["route"] == "research"
    assert client.chat.completions.create.call_count == 1
    out = assess_suitability(PAPER, PAPER, client=client, runs=3)
    assert client.chat.completions.create.call_count == 4
    assert out["consensus"]["runs"] == 3


def test_prompt_judges_problem_by_goal_not_motivation():
    assert "최종 목적" in SYSTEM_PROMPT and "후속 연구" in SYSTEM_PROMPT
