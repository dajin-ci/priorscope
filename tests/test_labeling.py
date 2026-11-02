"""eval/labeling.py 경로 라벨 테스트 (Studio·Solar 호출 없음)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

import labeling  # noqa: E402


def sheet(problem, scope, method, intuition):
    return {"problem": {"relation": problem}, "scope": {"relation": scope},
            "method": {"relation": method}, "route_intuition": intuition}


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
    assert merged["axes"]["scope"]["agreed"] is False and merged["axes"]["scope"]["relation"] is None
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
    text = (folder / "label_sheet.md").read_text(encoding="utf-8")
    assert "경로 라벨 기준" in text and "내 논문 problem" in text


def test_merge_route_only_when_comparison_blocked(tmp_path, monkeypatch):
    folder = _sample(tmp_path, monkeypatch)
    for name in ("a", "b"):
        (folder / f"route_{name}.json").write_text(json.dumps(
            sheet("different", "different", "different", "unsuitable")), encoding="utf-8")
    labeling.merge("S2")
    merged = json.loads((folder / "route_label.json").read_text())
    assert merged["expected_route"] == "unsuitable"
    assert not (folder / "labels.json").exists()


def test_manifest_is_consistent():
    manifest = json.loads((Path(__file__).resolve().parent.parent / "eval" / "samples" / "manifest.json")
                          .read_text(encoding="utf-8"))
    for sample_id, info in {**manifest["samples"], **manifest["optional"]}.items():
        assert info["label_mode"] in ("blind", "designed"), sample_id
        if info["label_mode"] == "designed":
            assert set(info["acceptable_routes"]) <= set(labeling.ROUTE_LABELS)
            assert info["preferred_route"] in info["acceptable_routes"]
