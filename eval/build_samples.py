"""
eval/build_samples.py

'샘플 결과 보기' 탭의 사례 묶음(samples/cases/)을 저장된 평가 결과로 다시 만든다.
API를 호출하지 않는다. 비교 단계까지 간 사례는 현재 validator 규칙으로 다시 검증해서,
규칙을 고친 뒤에도 화면에 지금 코드의 결과가 보이게 한다.

    python eval/build_samples.py

사례를 추가하려면 CASES에 한 줄 넣는다. source 는 eval/results/<버전>/<샘플> 이고,
추출 고정본(my_paper.json, prior_paper.json)은 eval/samples/<샘플>/ 에서 가져온다.
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from comparison_report import apply_scope_policy  # noqa: E402
from validator import combine_runs  # noqa: E402

OUT = ROOT / "samples" / "cases"

CASES = [
    {
        "key": "research",
        "label": "연구 내용 비교",
        "pair": "RoBERTa ↔ BERT",
        "source": "v11/S2",
        "look_for": "같은 문제를 다루는 후속 논문. 요소 대응표와 근거, 겹침 등급, 차별점 후보, "
                    "그리고 데이터셋·분할·구성이 모두 같은 실험만 골라 낸 정량 비교를 볼 수 있습니다.",
    },
    {
        "key": "partial_ko_en",
        "label": "공통 범위만 비교 · 국문↔영문",
        "pair": "한국어 리뷰 감성 분석 (JICS 2024) ↔ How to Fine-Tune BERT for Text Classification? (2019)",
        "source": "v11/S4",
        "look_for": "언어가 달라도 요소 대응이 유지되는지 보여주는 사례입니다. 문제 범위가 일부만 같아 "
                    "전체 등급과 차별점 목록은 일부러 보여주지 않고, 데이터셋이 달라 정량 비교는 0쌍입니다.",
    },
    {
        "key": "partial_method",
        "label": "공통 범위만 비교 · 방법 연결",
        "pair": "Open-Vocabulary Audio-Visual Event Localization ↔ ImageBind",
        "source": "v11/S1",
        "look_for": "내 논문이 기존 논문의 통합 임베딩 공간을 가져다 쓰는 경계 사례입니다. "
                    "가져다 쓴 방법 요소는 일치·유사로, 새 과제·데이터셋·평가 지표는 없음으로 나뉩니다.",
    },
    {
        "key": "unsuitable",
        "label": "비교 부적합",
        "pair": "DETR (물체 검출) ↔ Conformer (음성 인식)",
        "source": "v11/S3",
        "look_for": "Transformer라는 범용 기반만 같고 문제와 구체적 방법이 다른 쌍입니다. "
                    "요소 비교를 진행하지 않고, 왜 부적합한지와 다른 비교 대상을 고르라는 안내만 줍니다.",
    },
    {
        "key": "not_paper",
        "label": "비교 부적합 · 논문이 아닌 문서",
        "pair": "NVIDIA A100 GPU 아키텍처 백서 ↔ BERT",
        "source": "v11/S5",
        "look_for": "논문처럼 보이는 기술 백서입니다. 그럴듯한 기술 요소가 추출됐지만 실험 결과가 없고 "
                    "문제·범위·방법이 모두 달라 적합성 단계에서 멈춥니다.",
    },
    {
        "key": "insufficient",
        "label": "판단 보류",
        "pair": "Open-Vocabulary Audio-Visual Event Localization ↔ ImageBind (이전 버전 실행)",
        "source": "v7/S1",
        "look_for": "적합성 판단의 근거를 원문에서 확인하지 못한 기준이 있어 판단을 보류한 사례입니다. "
                    "무엇이 부족한지와 다시 분석하는 방법을 안내합니다. 적합성 판단 v1 시절 실행 결과입니다.",
    },
]


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(data, path):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_case(case):
    result_dir = ROOT / "eval" / "results" / case["source"]
    sample_dir = ROOT / "eval" / "samples" / case["source"].split("/")[1]
    out = OUT / case["key"]
    out.mkdir(parents=True, exist_ok=True)

    my, prior = _load(sample_dir / "my_paper.json"), _load(sample_dir / "prior_paper.json")
    suitability = _load(result_dir / "suitability.json")
    _save(my, out / "my_paper.json")
    _save(prior, out / "prior_paper.json")
    _save(suitability, out / "suitability.json")

    status = "-"
    runs_path = result_dir / "compare_result_runs.json"
    if suitability.get("comparison_allowed") and runs_path.exists():
        runs = _load(runs_path)
        old = _load(result_dir / "validated_result.json")
        similarity = _load(result_dir / "similarity.json") if (result_dir / "similarity.json").exists() else None
        verified = combine_runs(my, prior, runs, similarity=similarity,
                                failed_runs=old.get("consensus", {}).get("failed_runs", []))
        verified = apply_scope_policy(verified, suitability)
        _save(verified, out / "validated_result.json")
        _save(runs[verified["consensus"]["representative_run"] - 1], out / "compare_result.json")
        status = verified["status"]
    return {k: case[k] for k in ("key", "label", "pair", "source", "look_for")} | {
        "route": suitability["route"], "status": status}


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    index = [build_case(case) for case in CASES]
    _save({"note": "eval/build_samples.py 로 만든다. 직접 고치지 말 것.", "cases": index}, OUT / "cases.json")
    for c in index:
        print(f"{c['key']:16} route={c['route']:12} status={c['status']:13} ← {c['source']}")


if __name__ == "__main__":
    main()
