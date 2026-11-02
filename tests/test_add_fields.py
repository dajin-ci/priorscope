"""eval/add_fields.py 테스트 (Studio 호출 없음)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

import add_fields  # noqa: E402
import labeling  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def sample(tmp_path, monkeypatch):
    folder = tmp_path / "S1"
    folder.mkdir()
    for name in ("my_paper.json", "prior_paper.json", "labels.json"):
        (folder / name).write_text((ROOT / "eval" / "samples" / "S1" / name).read_text(encoding="utf-8"), encoding="utf-8")
    for module in (add_fields, labeling):
        monkeypatch.setattr(module, "SAMPLES_DIR", tmp_path)
        monkeypatch.setattr(module, "ROOT", tmp_path)
    return folder


def test_adds_only_requested_field_and_keeps_numbering(sample):
    before = json.loads((sample / "prior_paper.json").read_text())
    labels_before = (sample / "labels.json").read_text()
    new = dict(before, core_techniques=["[1] 완전히 다른 순서 | 바뀐 요소"],
               contributions=["[1] We bind six modalities with image-paired data only."])
    add_fields.add_fields("S1", "prior", new, ["contributions"])
    after = json.loads((sample / "prior_paper.json").read_text())
    assert after["contributions"] == new["contributions"]
    assert after["core_techniques"] == before["core_techniques"]
    assert (sample / "labels.json").read_text() == labels_before
    assert (sample / "reextract_prior_paper.json").exists()
    assert "We bind six modalities" in (sample / "label_sheet.md").read_text(encoding="utf-8")


def test_refuses_protected_fields(sample):
    with pytest.raises(ValueError):
        add_fields.add_fields("S1", "prior", {"core_techniques": ["x"]}, ["core_techniques"])


def test_empty_new_field_is_not_written(sample):
    add_fields.add_fields("S1", "prior", {"contributions": []}, ["contributions"])
    assert "contributions" not in json.loads((sample / "prior_paper.json").read_text())
