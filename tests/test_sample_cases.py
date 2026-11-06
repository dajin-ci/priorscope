"""samples/cases/ 사례 묶음이 화면에서 읽을 수 있는 상태인지 (eval/build_samples.py 결과)."""
import json
from pathlib import Path

CASES_DIR = Path(__file__).resolve().parent.parent / "samples" / "cases"


def _cases():
    return json.loads((CASES_DIR / "cases.json").read_text(encoding="utf-8"))["cases"]


def test_every_case_has_files_matching_its_route():
    for case in _cases():
        d = CASES_DIR / case["key"]
        for name in ("my_paper.json", "prior_paper.json", "suitability.json"):
            assert (d / name).exists(), f"{case['key']}: {name} 없음"
        suitability = json.loads((d / "suitability.json").read_text(encoding="utf-8"))
        assert suitability["route"] == case["route"]
        compared = (d / "validated_result.json").exists()
        assert compared == bool(suitability["comparison_allowed"]), case["key"]
        if compared:
            verified = json.loads((d / "validated_result.json").read_text(encoding="utf-8"))
            assert verified["status"] != "FAILED", f"{case['key']}: 샘플이 FAILED 결과입니다"


def test_cases_cover_main_routes():
    routes = {c["route"] for c in _cases()}
    assert {"research", "partial", "unsuitable", "insufficient"} <= routes
