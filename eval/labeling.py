"""
eval/labeling.py

정답 라벨 작업 도우미 (설계서 7장: 팀원 2명이 각자 라벨링, 의견이 갈린 요소는 확인필요)

1) 라벨 양식 만들기: 샘플 폴더의 my_paper.json, prior_paper.json 을 읽어
   라벨러별 빈 양식(labels_<이름>.json)과 참고용 요소 목록(label_sheet.md)을 만든다.
       python eval/labeling.py template S1 강다진 이건영

2) 두 사람 라벨 합치기: 같으면 그대로, 다르면 확인필요로 labels.json 을 만든다.
       python eval/labeling.py merge S1
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ids import assign_ids, first  # noqa: E402

SAMPLES_DIR = ROOT / "eval" / "samples"
VERDICTS = ("일치", "유사", "없음", "확인필요")

GUIDE = """## 라벨 기준

- 일치: 기존 논문에 같은 기법이 있다 (용어·언어가 달라도 같은 것)
- 유사: 기존 논문의 핵심 아이디어를 가져다 쓰거나 변형했다
- 없음: 기존 논문에 없다. Transformer 사용, 손실 함수 학습처럼 흔한 기법만 같으면 없음
- 확인필요: 논문을 다시 봐도 판단이 어렵다

각자 따로 라벨링하고 서로의 답을 보지 않는다. LLM 결과(compare_result)도 보지 않는다.
prior 에는 대응하는 P 번호를 적는다 (일치·유사일 때만, 없으면 빈 칸).
"""


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def template(sample: str, labelers: list[str]) -> None:
    folder = SAMPLES_DIR / sample
    my, prior = load(folder / "my_paper.json"), load(folder / "prior_paper.json")
    ids = assign_ids(my, prior)

    lines = [f"# {sample} 라벨 시트", "",
             f"- 내 논문: {first(my, 'title')}",
             f"- 기존 논문: {first(prior, 'title')}", "", GUIDE,
             "## 내 논문 요소 (M)", ""]
    lines += [f"- **{m['id']}** {m['text']}" for m in ids["M"]]
    lines += ["", "## 기존 논문 요소 (P)", ""]
    lines += [f"- **{p['id']}** {p['text']}" for p in ids["P"]]
    (folder / "label_sheet.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    blank = {m["id"]: {"verdict": "", "prior": [], "memo": ""} for m in ids["M"]}
    for name in labelers:
        path = folder / f"labels_{name}.json"
        if path.exists():
            print(f"  [유지] {path.name} 가 이미 있어 덮어쓰지 않았습니다.")
            continue
        path.write_text(json.dumps(blank, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [생성] {path.relative_to(ROOT)}")
    print(f"  [생성] {(folder / 'label_sheet.md').relative_to(ROOT)}  (M {len(ids['M'])}개, P {len(ids['P'])}개)")


def _verdict(entry) -> str:
    value = entry.get("verdict") if isinstance(entry, dict) else entry
    return value.strip() if isinstance(value, str) else ""


def merge(sample: str) -> None:
    folder = SAMPLES_DIR / sample
    files = sorted(folder.glob("labels_*.json"))
    if len(files) < 2:
        print("labels_<이름>.json 이 두 개 이상 있어야 합칠 수 있습니다.")
        sys.exit(1)
    sheets = {f.stem.removeprefix("labels_"): load(f) for f in files}
    m_ids = list(next(iter(sheets.values())))

    merged, disagreements, problems = {}, [], []
    for m_id in m_ids:
        answers = {name: _verdict(sheet.get(m_id, {})) for name, sheet in sheets.items()}
        bad = {n: v for n, v in answers.items() if v not in VERDICTS}
        if bad:
            problems.append(f"{m_id}: " + ", ".join(f"{n}='{v}'" for n, v in bad.items()))
            continue
        values = set(answers.values())
        if len(values) == 1:
            verdict = values.pop()
            priors = sorted({p for sheet in sheets.values() for p in (sheet[m_id].get("prior") or [])
                             if isinstance(sheet[m_id], dict)})
            merged[m_id] = {"verdict": verdict, "prior": priors}
        else:
            merged[m_id] = {"verdict": "확인필요", "prior": [], "disagreement": answers}
            disagreements.append(f"{m_id}: " + ", ".join(f"{n} {v}" for n, v in answers.items()))

    if problems:
        print("판정이 비었거나 허용값(일치·유사·없음·확인필요)이 아닌 칸이 있어 합치지 않았습니다.")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    (folder / "labels.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    agree = len(m_ids) - len(disagreements)
    print(f"  [생성] {(folder / 'labels.json').relative_to(ROOT)}")
    print(f"  라벨러 일치 {agree}/{len(m_ids)}개 ({agree / len(m_ids):.0%})")
    for d in disagreements:
        print(f"  의견 갈림 → 확인필요  {d}")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "template":
        template(sys.argv[2], sys.argv[3:])
    elif len(sys.argv) == 3 and sys.argv[1] == "merge":
        merge(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
