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
