"""
eval/evaluate.py

PriorScope 평가 (설계서 7장 + 10/31 적합성 분기 반영)

    # 1) 고정 추출본으로 3~7단계 실행 (API 사용: Solar 1회 + 비교 경로면 Compare Agent·임베딩)
    python eval/evaluate.py compare                    # 라벨이 있는 모든 샘플
    python eval/evaluate.py compare S1 S2 --tag v7     # 결과 폴더 이름 지정

    # 2) 저장된 결과를 라벨과 비교해 채점 (API 없음. 라벨을 고친 뒤 다시 채점할 때)
    python eval/evaluate.py score eval/results/<tag>

    # 3) 원본 PDF로 전체를 N번 돌려 흔들림 측정 (API 사용량이 가장 큼)
    #    PDF 이름: <pdf-dir>/S1_my.pdf, <pdf-dir>/S1_prior.pdf
    python eval/evaluate.py stability --pdf-dir ~/papers --runs 3 S1 S2

compare 는 결과를 eval/results/<tag>/<샘플>/ 에 저장하고 곧바로 채점해 report.json 을 만든다.
정답이 임시 라벨(label_status.json 의 provisional=true)이면 리포트 맨 위에 표시한다.
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAMPLES_DIR = ROOT / "eval" / "samples"
RESULTS_DIR = ROOT / "eval" / "results"
COMPARABLE = ("research", "partial", "method")
OVERLAP = ("일치", "유사")
# 설계서 7장 목표. 경로 지표는 10/31 분기 이후 추가한 목표다.
TARGETS = {
    "false_novelty_rate": ("<=", 0.10),
    "element_accuracy": (">=", 0.80),
    "route_accuracy": (">=", 0.80),
    "gate_leak_rate": ("<=", 0.0),
    "grade_agreement": (">=", 0.80),
}


##################################################
# 정답 읽기
##################################################

def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest() -> dict:
    data = _load(SAMPLES_DIR / "manifest.json")
    return {**data.get("samples", {}), **data.get("optional", {})}


def _verdict(value: Any) -> str:
    value = value.get("verdict") if isinstance(value, dict) else value
    return value.strip() if isinstance(value, str) else ""


def load_truth(sample: str, folder: Path | None = None, manifest: dict | None = None) -> dict | None:
    """샘플 정답을 모은다. 경로 정답이 없으면 None (채점 대상 아님)."""
    folder = folder or SAMPLES_DIR / sample
    info = (manifest if manifest is not None else _manifest()).get(sample, {})
    status = _load(folder / "label_status.json") if (folder / "label_status.json").exists() else {}

    if info.get("label_mode") == "designed":
        acceptable = list(info["acceptable_routes"])
        route = {"acceptable_routes": acceptable, "disputed": False, "from_sheet": None,
                 "comparison_expected": all(r in COMPARABLE for r in acceptable) if acceptable else None,
                 "axes": None}
        status = {"provisional": False, "labelers": ["designed"]}
    elif (folder / "route_label.json").exists():
        label = _load(folder / "route_label.json")
        route = {"acceptable_routes": label["acceptable_routes"], "disputed": label["disputed"],
                 "comparison_expected": label["comparison_expected"],
                 "from_sheet": (label.get("from_sheet") or {}).get("acceptable_routes"),
                 "axes": label.get("axes")}
    else:
        return None

    elements = None
    if (folder / "labels.json").exists():
        elements = {m_id: _verdict(v) for m_id, v in _load(folder / "labels.json").items()}

    grade = info.get("expected_grade")
    return {"sample": sample, "route": route, "elements": elements, "expected_grade": grade,
            "provisional": bool(status.get("provisional")), "labelers": status.get("labelers", [])}


##################################################
# 채점 (순수 함수)
##################################################

def score_sample(truth: dict, pred: dict) -> dict:
    """한 샘플 채점. pred 는 suitability, verified(없으면 None)를 담는다."""
    suit = pred["suitability"]
    route_pred = suit["route"]
    allowed_pred = bool(suit["comparison_allowed"])
    route = truth["route"]
    out: dict[str, Any] = {
        "sample": truth["sample"], "provisional": truth["provisional"],
        "route_pred": route_pred, "route_truth": route["acceptable_routes"],
        "route_correct": route_pred in route["acceptable_routes"],
        "route_disputed": route["disputed"],
        "route_correct_vs_sheet": (route_pred in route["from_sheet"]) if route["from_sheet"] else None,
        "gate_leak": route["comparison_expected"] is False and allowed_pred,
        "over_block": route["comparison_expected"] is True and not allowed_pred,
        "axes": {}, "elements": None, "grade": None,
    }

    if route["axes"]:
        for axis, info in route["axes"].items():
            pred_rel = suit.get("axes", {}).get(axis, {}).get("relation")
            out["axes"][axis] = {
                "pred": pred_rel, "truth": info.get("relation"), "truth_from_sheet": info.get("relation_from_sheet"),
                "correct": pred_rel == info.get("relation") if info.get("relation") else None,
                "correct_vs_sheet": (pred_rel == info.get("relation_from_sheet")
                                     if info.get("relation_from_sheet") else None),
            }

    verified = pred.get("verified")
    if verified and truth["elements"]:
        rows = []
        for mapping in verified.get("mappings", []):
            t = truth["elements"].get(mapping["id"])
            if not t:
                continue
            rows.append({"id": mapping["id"], "truth": t, "agent": mapping.get("agent_verdict"),
                         "final": mapping.get("final_verdict"),
                         "demoted": bool(mapping.get("demoted_reasons"))})
        missing = sorted(set(truth["elements"]) - {r["id"] for r in rows})
        out["elements"] = {"rows": rows, "missing_in_pred": missing}

    if truth["expected_grade"] and verified is not None and "research" in route["acceptable_routes"]:
        level = verified.get("final_level")
        held = level in (None, "판정 보류", "적용 안 함")
        out["grade"] = {"pred": level, "truth": truth["expected_grade"], "held": held,
                        "correct": None if held else level == truth["expected_grade"]}
    return out


def _rate(num: int, den: int) -> float | None:
    return num / den if den else None


def aggregate(scores: list[dict]) -> dict:
    confirmed = [s for s in scores if not s["route_disputed"]]
    disputed = [s for s in scores if s["route_disputed"]]
    gate_den = [s for s in scores if s["gate_leak"] or (s["route_truth"] and
                all(r not in COMPARABLE for r in s["route_truth"]))]
    pass_den = [s for s in scores if s["route_truth"] and all(r in COMPARABLE for r in s["route_truth"])]
    sheet = [s for s in confirmed if s["route_correct_vs_sheet"] is not None]

    axis_hits, axis_sheet_hits = Counter(), Counter()
    axis_den, axis_sheet_den = Counter(), Counter()
    for s in scores:
        for axis, a in s["axes"].items():
            if a["correct"] is not None:
                axis_den[axis] += 1
                axis_hits[axis] += a["correct"]
            if a["correct_vs_sheet"] is not None:
                axis_sheet_den[axis] += 1
                axis_sheet_hits[axis] += a["correct_vs_sheet"]

    rows = [r for s in scores if s["elements"] for r in s["elements"]["rows"]]
    overlap_rows = [r for r in rows if r["truth"] in OVERLAP]
    grades = [s["grade"] for s in scores if s["grade"]]
    decided = [g for g in grades if not g["held"]]

    return {
        "provisional": any(s["provisional"] for s in scores),
        "samples": len(scores),
        "route_accuracy": _rate(sum(s["route_correct"] for s in confirmed), len(confirmed)),
        "route_accuracy_disputed": _rate(sum(s["route_correct"] for s in disputed), len(disputed)),
        "route_accuracy_vs_sheet": _rate(sum(s["route_correct_vs_sheet"] for s in sheet), len(sheet)),
        "gate_leak_rate": _rate(sum(s["gate_leak"] for s in gate_den), len(gate_den)),
        "over_block_rate": _rate(sum(s["over_block"] for s in pass_den), len(pass_den)),
        "axis_accuracy": {a: _rate(axis_hits[a], axis_den[a]) for a in axis_den},
        "axis_accuracy_vs_sheet": {a: _rate(axis_sheet_hits[a], axis_sheet_den[a]) for a in axis_sheet_den},
        "elements_scored": len(rows),
        # 주 지표: 정답이 일치·유사인 M 중 최종 판정이 '없음'인 비율 (허위 신규 주장)
        "false_novelty_rate": _rate(sum(r["final"] == "없음" for r in overlap_rows), len(overlap_rows)),
        # 검증 전(Compare Agent 원판정) 허위 신규 주장률. 위 값과의 차이가 validator 의 효과다.
        "false_novelty_rate_agent": _rate(sum(r["agent"] == "없음" for r in overlap_rows), len(overlap_rows)),
        "element_accuracy": _rate(sum(r["final"] == r["truth"] for r in rows), len(rows)),
        "uncertain_rate": _rate(sum(r["final"] == "확인필요" for r in rows), len(rows)),
        "grade_agreement": _rate(sum(g["correct"] for g in decided), len(decided)),
        "grade_held": len(grades) - len(decided),
    }


def check_targets(metrics: dict) -> dict:
    result = {}
    for key, (op, goal) in TARGETS.items():
        value = metrics.get(key)
        result[key] = None if value is None else (value <= goal if op == "<=" else value >= goal)
    return result


##################################################
# 출력
##################################################

def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def print_report(report: dict) -> None:
    m, ok = report["metrics"], report["targets"]
    print()
    print("=" * 64)
    print("PriorScope 평가 리포트")
    print("=" * 64)
    if m["provisional"]:
        print("※ 임시 라벨(provisional) 기준입니다. 사람 라벨로 교체되기 전까지 참고용입니다.")
    print(f"샘플 {m['samples']}개 · 채점한 M 요소 {m['elements_scored']}개")
    print()
    label = {True: "달성", False: "미달", None: "측정 불가"}
    for key, (op, goal) in TARGETS.items():
        print(f"  {key:<26}{_pct(m[key]):>6}   목표 {op} {goal * 100:.0f}%   {label[ok[key]]}")
    print()
    print(f"  {'route_accuracy_vs_sheet':<26}{_pct(m['route_accuracy_vs_sheet']):>6}   (시트 기준 경로 대비, 판단 단계만)")
    print(f"  {'over_block_rate':<26}{_pct(m['over_block_rate']):>6}")
    print(f"  {'false_novelty_rate_agent':<26}{_pct(m['false_novelty_rate_agent']):>6}   (검증 전)")
    print(f"  {'uncertain_rate':<26}{_pct(m['uncertain_rate']):>6}")
    for axis, value in m["axis_accuracy"].items():
        sheet = m["axis_accuracy_vs_sheet"].get(axis)
        print(f"  axis {axis:<21}{_pct(value):>6}   (시트 기준 {_pct(sheet)})")
    print()
    print(f"  {'샘플':<6}{'예측 경로':<14}{'정답 경로':<26}{'결과'}")
    for s in report["samples"]:
        mark = "O" if s["route_correct"] else "X"
        if s["gate_leak"]:
            mark += " 게이트 누수"
        if s["over_block"]:
            mark += " 과잉 차단"
        print(f"  {s['sample']:<6}{s['route_pred']:<14}{'/'.join(s['route_truth']):<26}{mark}")
    print("=" * 64)


def build_report(scores: list[dict], extra: dict | None = None) -> dict:
    metrics = aggregate(scores)
    return {"created_at": datetime.now().isoformat(timespec="seconds"), "metrics": metrics,
            "targets": check_targets(metrics), "samples": scores, **(extra or {})}


##################################################
# 명령
##################################################

def _labeled_samples(requested: list[str]) -> list[str]:
    names = requested or sorted(p.name for p in SAMPLES_DIR.iterdir() if p.is_dir())
    manifest = _manifest()
    return [n for n in names if load_truth(n, manifest=manifest) is not None]


def score_dir(results: Path) -> dict:
    manifest = _manifest()
    scores = []
    for folder in sorted(p for p in results.iterdir() if p.is_dir()):
        truth = load_truth(folder.name, manifest=manifest)
        if truth is None or not (folder / "suitability.json").exists():
            continue
        verified_path = folder / "validated_result.json"
        pred = {"suitability": _load(folder / "suitability.json"),
                "verified": _load(verified_path) if verified_path.exists() else None}
        scores.append(score_sample(truth, pred))
    report = build_report(scores, {"results_dir": str(results)})
    (results / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_report(report)
    print(f"저장: {results / 'report.json'}")
    return report


def cmd_compare(samples: list[str], tag: str | None) -> dict:
    from service import run_from_extracted  # API 설정이 필요한 import 는 실행할 때만 한다
    from config import validate_config
    validate_config()
    targets = _labeled_samples(samples)
    if not targets:
        print("라벨(route_label.json 또는 designed)이 있는 샘플이 없습니다.")
        sys.exit(1)
    results = RESULTS_DIR / (tag or datetime.now().strftime("%Y%m%d-%H%M%S"))
    for sample in targets:
        out = results / sample
        out.mkdir(parents=True, exist_ok=True)
        my, prior = _load(SAMPLES_DIR / sample / "my_paper.json"), _load(SAMPLES_DIR / sample / "prior_paper.json")
        print(f"\n[{sample}] 3~7단계 실행")
        started = time.time()
        run_from_extracted(my, prior, out, on_step=lambda name: print("  ", name))
        (out / "timing.json").write_text(json.dumps({"seconds": round(time.time() - started, 1)}), encoding="utf-8")
    return score_dir(results)


def stability_summary(runs: list[dict]) -> dict:
    """같은 샘플을 여러 번 돌린 결과의 흔들림. runs 원소: n_m, n_p, route, final_level, seconds."""
    def spread(key):
        values = [r[key] for r in runs]
        return {"values": values, "min": min(values), "max": max(values)}
    return {
        "runs": len(runs),
        "m_count": spread("n_m"), "p_count": spread("n_p"),
        "routes": [r["route"] for r in runs],
        "route_consistent": len({r["route"] for r in runs}) == 1,
        "levels": [r["final_level"] for r in runs],
        "level_consistent": len({r["final_level"] for r in runs}) == 1,
        "seconds": [r["seconds"] for r in runs],
    }


def cmd_stability(samples: list[str], pdf_dir: Path, n: int, tag: str | None) -> dict:
    from service import run_compare_service
    from ids import as_list
    results = RESULTS_DIR / (tag or "stability-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    results.mkdir(parents=True, exist_ok=True)
    summary = {}
    for sample in samples:
        my_pdf, prior_pdf = pdf_dir / f"{sample}_my.pdf", pdf_dir / f"{sample}_prior.pdf"
        if not my_pdf.exists() or not prior_pdf.exists():
            print(f"[{sample}] 건너뜀: {my_pdf.name}, {prior_pdf.name} 이 {pdf_dir} 에 있어야 합니다.")
            continue
        runs = []
        for i in range(1, n + 1):
            print(f"\n[{sample}] {i}/{n}회")
            started = time.time()
            bundle = run_compare_service(my_pdf.read_bytes(), prior_pdf.read_bytes(),
                                         on_step=lambda name: print("  ", name))
            verified = bundle.get("verified") or {}
            runs.append({"run_dir": bundle["run_dir"], "seconds": round(time.time() - started, 1),
                         "n_m": len(as_list(bundle["my_paper"].get("core_techniques"))),
                         "n_p": len(as_list(bundle["prior_paper"].get("core_techniques"))),
                         "route": bundle["suitability"]["route"],
                         "final_level": verified.get("final_level")})
        summary[sample] = stability_summary(runs) | {"detail": runs}
        s = summary[sample]
        print(f"\n[{sample}] M {s['m_count']['values']} · P {s['p_count']['values']} · 경로 {s['routes']}"
              f" ({'일관' if s['route_consistent'] else '흔들림'}) · 등급 {s['levels']}")
    (results / "stability.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {results / 'stability.json'}")
    return summary


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("compare", "score", "stability"):
        print(__doc__)
        return 1
    command, rest = argv[0], argv[1:]

    def option(name, default=None):
        if name in rest:
            i = rest.index(name)
            value = rest[i + 1]
            del rest[i:i + 2]
            return value
        return default

    tag = option("--tag")
    if command == "score":
        if len(rest) != 1:
            print("사용법: python eval/evaluate.py score eval/results/<tag>")
            return 1
        score_dir(Path(rest[0]))
    elif command == "compare":
        cmd_compare(rest, tag)
    else:
        pdf_dir, runs = option("--pdf-dir"), int(option("--runs", "3"))
        if not pdf_dir or not rest:
            print("사용법: python eval/evaluate.py stability --pdf-dir <폴더> [--runs 3] S1 S2")
            return 1
        cmd_stability(rest, Path(pdf_dir).expanduser(), runs, tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
