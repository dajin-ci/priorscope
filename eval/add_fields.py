"""
eval/add_fields.py

고정된 샘플 추출본에 새 필드만 끼워 넣는다 (에이전트 스키마에 필드를 추가했을 때).

샘플의 my_paper.json / prior_paper.json 을 통째로 다시 추출하면 core_techniques 순서가
바뀌어 M·P 번호가 밀리고, 이미 만든 요소 라벨(labels.json)이 어긋난다. 그래서 새로
추출한 결과에서 지정한 필드만 가져와 고정본에 넣고, 번호를 만드는 필드는 건드리지 않는다.

    # 원본 PDF로 해당 에이전트를 다시 실행해 필드를 가져온다 (API 호출 1회)
    python eval/add_fields.py S1 prior ~/papers/ImageBind.pdf contributions

    # 이미 받아 둔 추출 JSON에서 가져온다 (API 호출 없음)
    python eval/add_fields.py S1 prior --from-json new_prior.json contributions

새 추출본 전체는 eval/samples/<샘플>/reextract_<side>_paper.json 에 남긴다
(core_techniques 가 얼마나 달라졌는지 비교하는 용도). 끝나면 label_sheet.md 를 다시 만든다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from ids import as_list  # noqa: E402

SAMPLES_DIR = ROOT / "eval" / "samples"
# M·P·R 번호를 만드는 필드. 바꾸면 라벨이 어긋나므로 거부한다.
PROTECTED = {"core_techniques", "experiment_results"}
SIDES = {"my": "my_paper.json", "prior": "prior_paper.json"}


def extract(side: str, pdf: Path) -> dict:
    from upload import upload_file
    if side == "my":
        from resume_agent import analyze_resume as analyze
    else:
        from jd_agent import analyze_jd as analyze
    result = analyze(upload_file(pdf))
    if not isinstance(result, dict):
        raise ValueError("에이전트 결과가 JSON 객체가 아닙니다.")
    return result


def add_fields(sample: str, side: str, new: dict, fields: list[str]) -> dict:
    blocked = sorted(set(fields) & PROTECTED)
    if blocked:
        raise ValueError(f"{', '.join(blocked)} 는 번호를 만드는 필드라 바꿀 수 없습니다. 라벨을 새로 만들어야 합니다.")
    folder = SAMPLES_DIR / sample
    target = folder / SIDES[side]
    fixed = json.loads(target.read_text(encoding="utf-8"))
    (folder / f"reextract_{SIDES[side]}").write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")

    added = {}
    for field in fields:
        values = as_list(new.get(field))
        if not values:
            print(f"  [경고] 새 추출본에 {field} 가 비어 있습니다. 에이전트 스키마에 필드를 추가했는지 확인하세요.")
            continue
        fixed[field] = values
        added[field] = values
    target.write_text(json.dumps(fixed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    old_core, new_core = as_list(fixed.get("core_techniques")), as_list(new.get("core_techniques"))
    if old_core != new_core:
        print(f"  [참고] 새 추출본의 core_techniques 는 고정본과 다릅니다 ({len(old_core)}개 → {len(new_core)}개)."
              " 고정본 번호를 유지했습니다.")
    for field, values in added.items():
        print(f"  [추가] {target.relative_to(ROOT)} ← {field} {len(values)}개")
        for value in values:
            print(f"     - {value}")

    import labeling
    labeling.template(sample, [])  # 라벨 파일은 그대로 두고 시트만 다시 만든다
    return added


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in SIDES:
        print(__doc__)
        return 1
    sample, side = argv[0], argv[1]
    from_json = argv[2] == "--from-json"
    source, fields = (argv[3] if len(argv) > 3 else None, argv[4:]) if from_json else (argv[2], argv[3:])
    # API 를 부르기 전에 인자를 모두 확인한다 (필드 이름을 빠뜨리면 호출 비용만 쓰고 끝나므로).
    if not source or not fields:
        print("가져올 필드 이름이 없습니다. 명령 끝에 필드 이름을 붙이세요.")
        print(f"  예) python eval/add_fields.py {sample} {side} {source or '<PDF 경로>'} contributions")
        return 1
    if not (SAMPLES_DIR / sample / SIDES[side]).exists():
        print(f"샘플 파일이 없습니다: eval/samples/{sample}/{SIDES[side]}")
        return 1
    if not Path(source).expanduser().exists():
        print(f"파일이 없습니다: {source}")
        return 1
    new = (json.loads(Path(source).expanduser().read_text(encoding="utf-8")) if from_json
           else extract(side, Path(source).expanduser()))
    try:
        add_fields(sample, side, new, fields)
    except ValueError as exc:
        print(f"중단: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
