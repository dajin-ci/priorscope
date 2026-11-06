"""
eval/focus_ab.py

관심 초점(체크박스)이 결과를 바꾸는지 확인하는 A/B 비교.

같은 추출 결과와 같은 적합성 판단을 고정하고 관심 초점만 바꿔서 5단계(Compare Agent)부터 돌린다.
체크 없이도 실행마다 출력이 흔들리므로, '체크 없음'을 여러 번 돌려 원래 흔들림부터 잰다.

    # 오늘 분석한 run 폴더의 추출 결과로, 체크 없음 2회 · 체크 있음 2회
    python eval/focus_ab.py runs/20261106-160952-d4eea6 --aspect architecture training --goal reviewer --repeat 2

    # 이미 돌린 결과만 다시 비교 (API 호출 없음)
    python eval/focus_ab.py --summarize eval/focus_ab/<시각>

판단 기준
- 관심 초점이 효과 있음: '체크 있음'의 관심 키워드 언급 비율이 '체크 없음' 여러 번의 범위보다 높다.
- 판정은 그대로여야 함: '체크 없음 ↔ 체크 있음' 판정 차이가 '체크 없음 ↔ 체크 없음' 차이보다 크지 않다.
"""

import argparse
import json
import sys
from datetime import datetime
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from focus import ASPECTS, GOALS, normalize  # noqa: E402

OUT = ROOT / "eval" / "focus_ab"

# 관심 항목별로 리포트 문장에 나오면 '그 항목을 다뤘다'고 보는 단어. 대략적인 지표다.
KEYWORDS = {
    "architecture": ["구조", "모듈", "아키텍처", "architecture", "레이어", "layer", "인코더", "encoder", "블록", "block"],
    "training": ["학습", "손실", "loss", "최적화", "미세 조정", "미세조정", "fine-tun", "사전학습", "pretrain", "training"],
    "data": ["데이터", "전처리", "증강", "라벨", "dataset", "corpus", "코퍼스"],
    "experiment": ["실험", "성능", "지표", "baseline", "기준선", "벤치마크", "benchmark", "정확도"],
    "efficiency": ["속도", "메모리", "파라미터", "비용", "효율", "latency", "연산량"],
    "problem": ["문제 설정", "과제", "도메인", "적용 분야", "task"],
    "related_work": ["Related Work", "관련 연구", "인용", "선행 연구"],
    "reviewer": ["리뷰어", "심사", "질문", "반박", "reviewer"],
    "next_step": ["후속", "향후", "확장", "한계", "future"],
}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(data, path):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


##################################################
# 실행
##################################################

def run_trials(source: Path, focus: dict, repeat: int, compare_runs: int, out_dir: Path) -> Path:
    import service

    my, prior = _load(source / "my_paper.json"), _load(source / "prior_paper.json")
    saved_suitability = source / "suitability.json"
    if saved_suitability.exists():
        # 적합성 판단도 흔들리므로 저장된 판단으로 고정한다 (Solar 호출도 줄어든다).
        fixed = _load(saved_suitability)
        service.assess_suitability = lambda *args, **kwargs: fixed
        if not fixed.get("comparison_allowed"):
            raise SystemExit(f"이 쌍은 경로가 {fixed['route']}라 요소 비교를 하지 않습니다. 비교 가능한 쌍을 고르세요.")

    out_dir.mkdir(parents=True, exist_ok=True)
    _save({"source": str(source), "focus": focus, "repeat": repeat, "compare_runs": compare_runs},
          out_dir / "plan.json")
    for condition, cond_focus in (("none", None), ("focus", focus)):
        for i in range(1, repeat + 1):
            trial = out_dir / f"{condition}_{i}"
            trial.mkdir()
            print(f"[{condition} {i}/{repeat}] 실행 중...")
            service.run_from_extracted(my, prior, trial, on_step=lambda name: print("   ", name),
                                       compare_runs=compare_runs, focus=cond_focus)
    return out_dir


##################################################
# 비교 (API 호출 없음)
##################################################

def _report_sentences(trial: Path) -> list[str]:
    compare = _load(trial / "compare_result.json")
    return [str(x) for x in (compare.get("caution_points") or []) + (compare.get("differentiation_suggestions") or [])]


def _verdicts(trial: Path) -> dict:
    return {m["id"]: m["final_verdict"] for m in _load(trial / "validated_result.json")["mappings"]}


def _hit_rate(sentences: list[str], key: str) -> float:
    if not sentences:
        return 0.0
    words = [w.lower() for w in KEYWORDS[key]]
    return sum(any(w in s.lower() for w in words) for s in sentences) / len(sentences)


def _verdict_diff(a: dict, b: dict) -> int:
    return sum(a.get(k) != b.get(k) for k in set(a) | set(b))


def summarize(out_dir: Path) -> dict:
    plan = _load(out_dir / "plan.json")
    focus = normalize(plan["focus"])
    keys = focus["aspects"] + focus["goals"]
    trials = {c: sorted(out_dir.glob(f"{c}_*")) for c in ("none", "focus")}
    trials = {c: [t for t in ts if (t / "validated_result.json").exists()] for c, ts in trials.items()}
    if not trials["none"] or not trials["focus"]:
        raise SystemExit("비교할 실행이 부족합니다 (none_*, focus_* 폴더에 validated_result.json 필요).")

    rates = {c: {k: [round(_hit_rate(_report_sentences(t), k), 2) for t in ts] for k in keys}
             for c, ts in trials.items()}
    verdicts = {c: [_verdicts(t) for t in ts] for c, ts in trials.items()}
    noise = [_verdict_diff(a, b) for a, b in combinations(verdicts["none"], 2)]
    cross = [_verdict_diff(a, b) for a in verdicts["none"] for b in verdicts["focus"]]

    print("\n관심 키워드 언급 비율 (주의 지점 + 서술 제안 문장 중)")
    print(f"{'항목':22} {'체크 없음':>16} {'체크 있음':>16}  판단")
    effects = {}
    for k in keys:
        label = (ASPECTS.get(k) or GOALS.get(k))[0]
        none_max = max(rates["none"][k])
        focus_min = min(rates["focus"][k])
        effects[k] = "효과 있음" if focus_min > none_max else "구분 안 됨"
        print(f"{label:22} {str(rates['none'][k]):>16} {str(rates['focus'][k]):>16}  {effects[k]}")

    print("\n요소 판정 차이 (다르게 판정된 M 개수)")
    print(f"  체크 없음 ↔ 체크 없음 (원래 흔들림): {noise if noise else '반복 1회라 측정 불가'}")
    print(f"  체크 없음 ↔ 체크 있음              : {cross}")
    verdict_ok = (max(cross) <= max(noise)) if noise else None
    if verdict_ok is None:
        print("  → 원래 흔들림을 재려면 --repeat 2 이상으로 돌리세요.")
    else:
        print("  → 판정은 관심 초점과 무관하게 유지" if verdict_ok else
              "  → 관심 초점이 판정까지 흔든 것으로 보임 (원래 흔들림보다 큼). 확인 필요")

    print("\n서술 제안 원문 (사람이 읽고 판단)")
    for c, ts in trials.items():
        for t in ts:
            suggestions = _load(t / "compare_result.json").get("differentiation_suggestions") or []
            print(f"\n[{t.name}]")
            for s in suggestions:
                print(f"  - {s}")

    result = {"focus": focus, "keyword_rates": rates, "effects": effects,
              "verdict_noise": noise, "verdict_cross": cross, "verdict_unchanged": verdict_ok}
    _save(result, out_dir / "summary.json")
    print(f"\n저장: {out_dir / 'summary.json'}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", nargs="?", help="my_paper.json·prior_paper.json(·suitability.json)이 있는 폴더")
    parser.add_argument("--aspect", nargs="*", default=[], choices=list(ASPECTS))
    parser.add_argument("--goal", nargs="*", default=[], choices=list(GOALS))
    parser.add_argument("--repeat", type=int, default=2, help="조건별 반복 횟수 (기본 2: 원래 흔들림 측정)")
    parser.add_argument("--compare-runs", type=int, default=1,
                        help="한 번 실행할 때 Compare Agent 횟수 (기본 1: 크레딧 절약, 서비스 기본은 3)")
    parser.add_argument("--summarize", help="이미 돌린 결과 폴더만 다시 비교")
    parser.add_argument("--yes", action="store_true", help="확인 없이 바로 실행")
    args = parser.parse_args()

    if args.summarize:
        summarize(Path(args.summarize))
        return
    if not args.source or not (args.aspect or args.goal):
        parser.error("source 폴더와 --aspect 또는 --goal 을 하나 이상 주세요.")

    focus = {"aspects": args.aspect, "goals": args.goal}
    calls = 2 * args.repeat * args.compare_runs
    print(f"Studio Compare Agent 호출 {calls}회 예정 (체크 없음 {args.repeat}회 + 체크 있음 {args.repeat}회, "
          f"각 {args.compare_runs}회). 추출과 적합성 판단은 저장된 결과를 씁니다.")
    if not args.yes and input("진행할까요? [y/N] ").strip().lower() != "y":
        return
    out_dir = run_trials(Path(args.source), focus, args.repeat, args.compare_runs,
                         OUT / datetime.now().strftime("%Y%m%d-%H%M%S"))
    summarize(out_dir)


if __name__ == "__main__":
    main()
