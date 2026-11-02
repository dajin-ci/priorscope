"""eval/labeling.py 경로 라벨 테스트 (Studio·Solar 호출 없음)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

import labeling  # noqa: E402


def sheet(problem, scope, method, intuition, from_sheet=None):
    """from_sheet 를 주지 않으면 시트 기준 관계를 실제 관계와 같게 둔다."""
    from_sheet = from_sheet or (problem, scope, method)
    return {axis: {"relation": actual, "relation_from_sheet": seen}
            for axis, actual, seen in zip(("problem", "scope", "method"), (problem, scope, method), from_sheet)
            } | {"route_intuition": intuition}


def test_route_of_uses_select_route_rules():
    assert labeling.route_of(sheet("same", "comparable", "specific_shared", "research"))[0] == "research"
    assert labeling.route_of(sheet("related", "partial", "different", "partial"))[0] == "partial"
    assert labeling.route_of(sheet("different", "unknown", "specific_shared", "method"))[0] == "method"
    assert labeling.route_of(sheet("different", "different", "generic_only", "unsuitable"))[0] == "unsuitable"
    assert labeling.route_of(sheet("unknown", "unknown", "unknown", "insufficient"))[0] == "insufficient"


def test_route_of_rejects_blank_or_invalid_relation():
    route, problem = labeling.route_of(sheet("", "comparable", "different", "research"))
    assert route is None and "problem" in problem
    route, problem = labeling.route_of(sheet("same", "similar", "different", "research"))
    assert route is None and "scope" in problem


def test_merge_agreeing_routes_even_if_axes_differ():
    merged, problems = labeling.merge_routes({
        "a": sheet("different", "different", "generic_only", "unsuitable"),
        "b": sheet("different", "partial", "different", "unsuitable"),
    })
    assert not problems
    assert merged["expected_route"] == "unsuitable" and not merged["disputed"]
    assert merged["comparison_expected"] is False
    assert merged["axes"]["scope"]["relation_agreed"] is False and merged["axes"]["scope"]["relation"] is None
    assert merged["route_changed_by_extraction"] is False
    assert merged["needs_element_labels"] is False


def test_merge_disputed_route_keeps_all_and_flags_mixed_gate():
    merged, _ = labeling.merge_routes({
        "a": sheet("different", "unknown", "specific_shared", "method"),
        "b": sheet("different", "unknown", "generic_only", "method"),
    })
    assert merged["disputed"] and merged["expected_route"] is None
    assert merged["acceptable_routes"] == ["method", "unsuitable"]
    assert merged["comparison_expected"] is None
    assert merged["intuition_mismatch"] == ["b"]
    assert merged["needs_element_labels"] is True


def test_merge_reports_invalid_intuition():
    merged, problems = labeling.merge_routes({
        "a": sheet("same", "comparable", "specific_shared", ""),
        "b": sheet("same", "comparable", "specific_shared", "research"),
    })
    assert merged is None and problems and problems[0].startswith("a:")


def _sample(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parent.parent
    folder = tmp_path / "S2"
    folder.mkdir()
    for name in ("my_paper.json", "prior_paper.json"):
        (folder / name).write_text((root / "eval" / "samples" / "S2" / name).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(labeling, "SAMPLES_DIR", tmp_path)
    monkeypatch.setattr(labeling, "ROOT", tmp_path)
    return folder


def test_template_creates_route_sheets_and_keeps_existing(tmp_path, monkeypatch):
    folder = _sample(tmp_path, monkeypatch)
    (folder / "route_a.json").write_text('{"keep": true}', encoding="utf-8")
    labeling.template("S2", ["a", "b"])
    assert json.loads((folder / "route_a.json").read_text()) == {"keep": True}
    blank = json.loads((folder / "route_b.json").read_text())
    assert set(blank) == {"problem", "scope", "method", "route_intuition", "memo"}
    assert set(blank["problem"]) == {"relation", "relation_from_sheet", "memo"}
    text = (folder / "label_sheet.md").read_text(encoding="utf-8")
    assert "경로 라벨 기준" in text and "내 논문 problem" in text
    assert "기존 논문 experiment_results" in text


def test_merge_route_only_when_comparison_blocked(tmp_path, monkeypatch):
    folder = _sample(tmp_path, monkeypatch)
    for name in ("a", "b"):
        (folder / f"route_{name}.json").write_text(json.dumps(
            sheet("different", "different", "different", "unsuitable")), encoding="utf-8")
    labeling.merge("S2")
    merged = json.loads((folder / "route_label.json").read_text())
    assert merged["expected_route"] == "unsuitable"
    assert not (folder / "labels.json").exists()
    assert json.loads((folder / "label_status.json").read_text())["provisional"] is False


def test_extraction_gap_changes_route():
    merged, _ = labeling.merge_routes({
        "a": sheet("related", "partial", "specific_shared", "partial",
                   from_sheet=("different", "partial", "specific_shared")),
        "b": sheet("related", "partial", "specific_shared", "partial"),
    })
    assert merged["expected_route"] == "partial"
    assert merged["axes"]["problem"]["extraction_gap"] is True
    assert merged["axes"]["method"]["extraction_gap"] is False
    assert merged["from_sheet"]["acceptable_routes"] == ["partial", "method"]
    assert merged["route_changed_by_extraction"] is True


def test_missing_sheet_relation_is_reported():
    broken = sheet("same", "comparable", "specific_shared", "research")
    broken["scope"]["relation_from_sheet"] = ""
    merged, problems = labeling.merge_routes({"a": broken, "b": broken})
    assert merged is None and "scope.relation_from_sheet" in problems[0]


def test_provisional_merge_with_one_labeler_and_blank_forms_ignored(tmp_path, monkeypatch):
    folder = _sample(tmp_path, monkeypatch)
    labeling.template("S2", ["kim", "claude"])  # kim 의 양식은 빈 채로 둔다
    (folder / "route_claude.json").write_text(json.dumps(
        sheet("same", "comparable", "specific_shared", "research")), encoding="utf-8")
    labels = json.loads((folder / "labels_claude.json").read_text())
    for m_id in labels:
        labels[m_id] = {"verdict": "없음", "prior": []}
    (folder / "labels_claude.json").write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")

    labeling.merge("S2", provisional=True)
    status = json.loads((folder / "label_status.json").read_text())
    assert status == status | {"provisional": True, "labelers": ["claude"]}
    assert json.loads((folder / "route_label.json").read_text())["expected_route"] == "research"
    assert set(json.loads((folder / "labels.json").read_text())) == set(labels)


def test_non_provisional_merge_refuses_single_labeler(tmp_path, monkeypatch):
    folder = _sample(tmp_path, monkeypatch)
    (folder / "route_claude.json").write_text(json.dumps(
        sheet("same", "comparable", "specific_shared", "research")), encoding="utf-8")
    import pytest
    with pytest.raises(SystemExit):
        labeling.merge("S2")


def test_manifest_is_consistent():
    manifest = json.loads((Path(__file__).resolve().parent.parent / "eval" / "samples" / "manifest.json")
                          .read_text(encoding="utf-8"))
    for sample_id, info in {**manifest["samples"], **manifest["optional"]}.items():
        assert info["label_mode"] in ("blind", "designed"), sample_id
        if info["label_mode"] == "designed":
            assert set(info["acceptable_routes"]) <= set(labeling.ROUTE_LABELS)
            assert info["preferred_route"] in info["acceptable_routes"]
