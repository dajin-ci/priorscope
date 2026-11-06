"""Studio Extract가 단일 값 필드에 같은 값을 반복해 낸 경우 (samples S2 v11 FAILED 원인)."""

def test_repeated_identical_single_values_are_collapsed_not_failed():
    from validator import _collapse_repeated_singles
    raw = {"overlap_level": ["Medium Overlap"] * 3, "summary": ["a  b", "a b"], "llm_score": [64]}
    out, collapsed = _collapse_repeated_singles(raw)
    assert out["overlap_level"] == ["Medium Overlap"] and out["summary"] == ["a  b"]
    assert sorted(collapsed) == [("overlap_level", 3), ("summary", 2)]
    assert raw["overlap_level"] == ["Medium Overlap"] * 3  # 원본은 그대로


def test_different_single_values_still_fail():
    from validator import _collapse_repeated_singles
    out, collapsed = _collapse_repeated_singles({"overlap_level": ["Medium Overlap", "High Overlap"]})
    assert collapsed == [] and len(out["overlap_level"]) == 2


##################################################
# "해당 없음" 표시 줄, 나뉜 서술 필드 (v9 S1, v10 S4, v11 S1 FAILED 원인)
##################################################

def test_no_pair_marker_lines_become_empty_list():
    from validator import _normalize_agent_output
    raw = {"result_pairs": ["해당 없음 | 조건 다름 | 데이터셋이 다름"]}
    out, notes = _normalize_agent_output(raw)
    assert out["result_pairs"] == []
    assert [n["code"] for n in notes] == ["RESULT_PAIRS_NONE_MARKER"] and notes[0]["severity"] == "info"
    assert raw["result_pairs"] == ["해당 없음 | 조건 다름 | 데이터셋이 다름"]  # 원본은 그대로


def test_broken_line_with_ids_is_not_dropped():
    from validator import _normalize_agent_output
    raw = {"result_pairs": ["없음 R-M1 ~ R-P2 깨진 줄", "R-M1 ~ R-P1 | 동일 조건 | x"]}
    out, notes = _normalize_agent_output(raw)
    assert out["result_pairs"] == raw["result_pairs"] and notes == []


def test_split_text_fields_are_joined_but_level_stays_strict():
    from validator import _normalize_agent_output
    raw = {"summary": ["첫 문장.", "둘째 문장."], "related_work_draft": ["A", "B"],
           "overlap_level": ["Medium Overlap", "High Overlap"]}
    out, notes = _normalize_agent_output(raw)
    assert out["summary"] == ["첫 문장. 둘째 문장."] and out["related_work_draft"] == ["A B"]
    assert out["overlap_level"] == ["Medium Overlap", "High Overlap"]
    assert {n["code"] for n in notes} == {"TEXT_FIELD_JOINED"}


def test_none_marker_result_no_longer_fails_validation():
    from test_suitability import PAPER
    from validator import validate
    compare = {
        "overlap_level": ["Low Overlap"], "llm_score": [20], "summary": ["s"], "related_work_draft": ["d"],
        "element_mapping": [], "result_pairs": ["해당 없음"], "caution_points": ["c"],
        "differentiation_suggestions": ["a", "b", "c"],
    }
    result = validate(PAPER, PAPER, compare)
    assert not any(i["code"] == "RESULT_PAIR_FORMAT_INVALID" for i in result["issues"])
    assert any(i["code"] == "RESULT_PAIRS_NONE_MARKER" for i in result["issues"])
