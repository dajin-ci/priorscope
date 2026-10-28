"""
eval/calibrate_similarity.py

정답 라벨로 임베딩 유사도 임계값을 정한다. (멘토링 10/27 #8 "유사도 score 평가 기준 정의")

점수의 의미
  각 M의 점수 = 그 M과 가장 비슷한 P 요소의 코사인 유사도(max_score).
  정답이 일치·유사인 M(실제로 기존 논문에 있는 것)은 점수가 높고,
  정답이 없음인 M(진짜 고유 요소)은 점수가 낮아야 이 지표가 쓸모 있다.

임계값의 역할
  validator는 LLM이 '없음'이라 했는데 점수가 임계값 이상이면 '확인필요'로 강등한다.
  - 임계값이 낮을수록 허위 신규 주장을 더 많이 잡는다 (재현율↑)
  - 대신 진짜 고유 요소도 확인필요로 내려가 판정 보류가 늘어난다 (오경보↑)
  그래서 "오경보율이 목표 이하인 범위에서 재현율이 가장 높은 값"을 고른다.

폴더 구조 (샘플마다)
  eval/samples/S1/my_paper.json
  eval/samples/S1/prior_paper.json
  eval/samples/S1/labels.json        {"M1": "없음", "M2": {"verdict": "유사", "prior": ["P3"]}, ...}
  eval/samples/S1/similarity.json    (없으면 --compute 로 만든다)

사용법 (프로젝트 폴더에서):
    python eval/calibrate_similarity.py --compute
    python eval/calibrate_similarity.py --max-false-alarm 0.2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAMPLES_DIR = ROOT / "eval" / "samples"
OUT_PATH = ROOT / "eval" / "similarity_threshold.json"
POSITIVE = {"일치", "유사"}
NEGATIVE = {"없음"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def label_of(value) -> str | None:
    """labels.json 값은 "없음" 같은 문자열이거나 {"verdict": "유사", ...} 객체다."""
    if isinstance(value, dict):
        value = value.get("verdict")
    return value if isinstance(value, str) else None


def collect_points(samples_dir: Path, compute: bool = False, embedder=None) -> list[dict]:
    """샘플마다 (점수, 정답) 쌍을 모은다. 확인필요 정답은 기준이 없어서 뺀다."""
    points = []
    for sample in sorted(p for p in samples_dir.iterdir() if p.is_dir()):
        labels_path = sample / "labels.json"
        if not labels_path.exists():
            print(f"  [건너뜀] {sample.name}: labels.json 없음")
            continue
        sim_path = sample / "similarity.json"
        if not sim_path.exists() or compute:
            if not compute:
                print(f"  [건너뜀] {sample.name}: similarity.json 없음 (--compute 로 만드세요)")
                continue
            from similarity import UpstageEmbedder, compute_similarity

            sim = compute_similarity(load(sample / "my_paper.json"), load(sample / "prior_paper.json"),
                                     embedder or UpstageEmbedder())
            sim_path.write_text(json.dumps(sim, ensure_ascii=False, indent=2), encoding="utf-8")
        sim = load(sim_path)
        scores = {row["id"]: row["max_score"] for row in sim.get("per_m", [])}
        for m_id, value in load(labels_path).items():
            gold = label_of(value)
            if m_id in scores and gold in POSITIVE | NEGATIVE:
                points.append({"sample": sample.name, "id": m_id, "score": scores[m_id],
                               "positive": gold in POSITIVE})
    return points


def auc(points: list[dict]) -> float | None:
    """정답 일치·유사 M의 점수가 정답 없음 M보다 높을 확률. 0.5면 구분 못 함, 1.0이면 완벽."""
    pos = [p["score"] for p in points if p["positive"]]
    neg = [p["score"] for p in points if not p["positive"]]
    if not pos or not neg:
        return None
    wins = sum(1.0 if a > b else 0.5 if a == b else 0.0 for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def sweep(points: list[dict], start=0.30, stop=0.95, step=0.01) -> list[dict]:
    pos = sum(p["positive"] for p in points)
    neg = len(points) - pos
    rows = []
    t = start
    while t <= stop + 1e-9:
        tp = sum(p["positive"] and p["score"] >= t for p in points)
        fp = sum((not p["positive"]) and p["score"] >= t for p in points)
        rows.append({
            "threshold": round(t, 2),
            "recall": tp / pos if pos else None,          # 실제로 겹치는 M 중 잡아낸 비율
            "false_alarm": fp / neg if neg else None,     # 진짜 고유 M 중 확인필요로 잘못 내린 비율
        })
        t += step
    return rows


def recommend(rows: list[dict], max_false_alarm: float) -> dict | None:
    ok = [r for r in rows if r["false_alarm"] is not None and r["false_alarm"] <= max_false_alarm
          and r["recall"] is not None]
    if not ok:
        return None
    best_recall = max(r["recall"] for r in ok)
    # 같은 재현율이면 오경보가 적은(임계값이 높은) 쪽을 고른다.
    return max((r for r in ok if r["recall"] == best_recall), key=lambda r: r["threshold"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", default=str(SAMPLES_DIR))
    parser.add_argument("--compute", action="store_true", help="similarity.json 을 새로 계산")
    parser.add_argument("--max-false-alarm", type=float, default=0.2)
    args = parser.parse_args()

    points = collect_points(Path(args.samples), compute=args.compute)
    pos = sum(p["positive"] for p in points)
    neg = len(points) - pos
    print(f"\n라벨된 M 요소 {len(points)}개 (일치·유사 {pos}, 없음 {neg})")
    if not pos or not neg:
        print("일치·유사와 없음 정답이 모두 있어야 임계값을 정할 수 있습니다.")
        sys.exit(1)

    separation = auc(points)
    print(f"구분력(AUC) {separation:.3f}  (0.5 = 구분 못 함, 0.8 이상이면 쓸 만함)")

    rows = sweep(points)
    print("\n임계값  재현율  오경보율")
    for r in rows:
        if round(r["threshold"] * 100) % 5 == 0:
            print(f"  {r['threshold']:.2f}   {r['recall']:.2f}    {r['false_alarm']:.2f}")

    best = recommend(rows, args.max_false_alarm)
    if best is None:
        print(f"\n오경보율 {args.max_false_alarm:.0%} 이하를 만족하는 임계값이 없습니다.")
        sys.exit(1)

    print(f"\n추천 임계값 {best['threshold']:.2f} → 재현율 {best['recall']:.2f}, 오경보율 {best['false_alarm']:.2f}")
    print(f".env 에 추가: SIMILARITY_DEMOTE_THRESHOLD={best['threshold']:.2f}")

    OUT_PATH.write_text(json.dumps({
        "recommended": best,
        "max_false_alarm": args.max_false_alarm,
        "auc": separation,
        "n_points": len(points),
        "n_positive": pos,
        "n_negative": neg,
        "sweep": rows,
        "points": points,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
