"""
eval/labeling.py

정답 라벨 작업 도우미 (설계서 7장: 팀원 2명이 각자 라벨링, 의견이 갈린 요소는 확인필요)

1) 라벨 양식 만들기: 샘플 폴더의 my_paper.json, prior_paper.json 을 읽어
   라벨러별 빈 양식(labels_<이름>.json)과 참고용 요소 목록(label_sheet.md)을 만든다.
       python eval/labeling.py template S1 강다진 이건영

2) 두 사람 라벨 합치기: 같으면 그대로, 다르면 확인필요로 labels.json 을 만든다.
       python eval/labeling.py merge S1

3) 임시 라벨: 라벨러가 한 명(예: LLM)뿐일 때 임시로 합친다. label_status.json 에
   provisional=true 와 라벨러를 남기고, 사람 라벨 두 개로 merge 하면 false 로 바뀐다.
       python eval/labeling.py merge S1 --provisional

경로 라벨 (비교 적합성, 10/31 분기 구조 반영)
- template 은 요소 라벨 양식과 함께 라벨러별 route_<이름>.json 도 만든다.
- 라벨러는 경로를 직접 고르지 않고 세 축(문제·범위·방법)의 관계를 고른다.
  정답 경로는 suitability.select_route 와 같은 규칙으로 코드가 계산한다.
- 축마다 relation(원문을 알고 내린 실제 관계, 정답)과 relation_from_sheet(시트만 읽었을 때의
  관계)를 함께 받는다. 둘이 다르면 추출 단계가 정보를 놓친 것이고, 평가에서
  추출 오류와 판단 오류를 나눠 세는 데 쓴다.
- route_intuition 에는 규칙을 생각하지 않고 직감으로 고른 경로를 적는다.
  계산 경로와 다르면 merge 가 알려 주며, 경로 규칙 자체를 점검하는 자료로 쓴다.
- merge 는 route_label.json 을 만든다. 라벨러끼리 경로가 갈리면 acceptable_routes 에
  모두 남기고 disputed=true 로 표시한다 (평가에서 별도 집계).
- labels.json 형식은 바꾸지 않는다 (calibrate_similarity.py 가 그대로 읽는다).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ids import as_list, assign_ids, first  # noqa: E402
from suitability import AXIS_LABELS, RELATIONS, ROUTE_LABELS, select_route  # noqa: E402

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

COMPARABLE_ROUTES = ("research", "partial", "method")

ROUTE_GUIDE = """## 경로 라벨 기준 (route_<이름>.json)

경로를 직접 고르지 말고 세 축의 관계를 고른다. 경로는 코드가 계산한다.
축마다 두 값을 적는다.
- relation: 원문 PDF까지 알고 내린 실제 관계 (정답으로 쓴다)
- relation_from_sheet: 이 시트만 읽었을 때의 관계 (모델이 보는 자료와 같다)
시트만 읽으면 달라 보이지만 원문을 알면 연결되는 경우, 두 값을 다르게 적고 memo 에 이유를 남긴다.

- problem (해결 문제·목적)
  - same: 같은 문제를 푼다 / related: 연관되지만 다른 문제 / different: 연결 없음 / unknown: 판단 불가
  - 분야 이름이나 키워드가 같다는 이유만으로 same 을 고르지 않는다.
- scope (연구 범위·대상: 입출력, 연구 대상, 전제 조건)
  - comparable: 연구 내용을 견줄 수 있을 만큼 대응 / partial: 일부만 공통 / different: 다름 / unknown
  - 실험 조건이 같은지와는 별개다.
- method (핵심 방법)
  - specific_shared: 구체적 기법·모듈·학습 절차를 공유·변형·확장
  - generic_only: Transformer, 딥러닝 같은 범용 기반만 공통 / different: 연결 없음 / unknown
- route_intuition: 규칙을 떠올리지 말고 직감으로 고른 경로
  (research, partial, method, unsuitable, insufficient 중 하나)

경로 계산 규칙 (suitability.select_route):
problem=same 이고 scope=comparable → research, scope=partial·different → partial /
problem=related 이고 scope 판단 가능 → partial /
problem=different 이고 method=specific_shared → method, generic_only·different → unsuitable /
그 밖 → insufficient
"""


RELATION_KEYS = ("relation", "relation_from_sheet")


def _blank_route_sheet() -> dict:
    sheet = {axis: {"relation": "", "relation_from_sheet": "", "memo": ""} for axis in RELATIONS}
    sheet["route_intuition"] = ""
    sheet["memo"] = ""
    return sheet


def _relation(sheet, axis, key="relation") -> str:
    entry = sheet.get(axis) if isinstance(sheet, dict) else None
    value = entry.get(key) if isinstance(entry, dict) else (entry if key == "relation" else None)
    return value.strip() if isinstance(value, str) else ""


def route_of(sheet, key: str = "relation") -> tuple[str | None, str | None]:
    """라벨러 한 명의 세 축 관계로 경로를 계산한다. 형식이 틀리면 (None, 문제 설명).

    key="relation" 은 실제 관계, key="relation_from_sheet" 는 시트 기준 관계로 계산한다.
    """
    if not isinstance(sheet, dict):
        return None, "양식이 객체가 아닙니다"
    axes = {}
    for axis, allowed in RELATIONS.items():
        relation = _relation(sheet, axis, key)
        if relation not in allowed:
            return None, f"{axis}.{key}='{relation}' (허용값: {', '.join(allowed)})"
        axes[axis] = {"relation": relation}
    return select_route(axes), None


def _combine(routes: dict[str, str]) -> dict:
    acceptable = sorted(set(routes.values()), key=list(ROUTE_LABELS).index)
    allowed_flags = {route in COMPARABLE_ROUTES for route in acceptable}
    return {
        "expected_route": acceptable[0] if len(acceptable) == 1 else None,
        "acceptable_routes": acceptable,
        "disputed": len(acceptable) > 1,
        # 라벨러 전원이 비교 진행/차단에 동의할 때만 True/False. 섞이면 None.
        "comparison_expected": allowed_flags.pop() if len(allowed_flags) == 1 else None,
    }


def merge_routes(sheets: dict[str, dict]) -> tuple[dict | None, list[str]]:
    """라벨러별 route 양식을 합친다. 반환: (route_label, 형식 문제 목록)."""
    problems, routes, sheet_routes, intuitions = [], {}, {}, {}
    for name, sheet in sheets.items():
        route, problem = route_of(sheet)
        sheet_route, sheet_problem = route_of(sheet, "relation_from_sheet")
        if problem or sheet_problem:
            problems.extend(f"{name}: {p}" for p in (problem, sheet_problem) if p)
            continue
        intuition = sheet.get("route_intuition")
        intuition = intuition.strip() if isinstance(intuition, str) else ""
        if intuition not in ROUTE_LABELS:
            problems.append(f"{name}: route_intuition='{intuition}' (허용값: {', '.join(ROUTE_LABELS)})")
            continue
        routes[name], sheet_routes[name], intuitions[name] = route, sheet_route, intuition
    if problems:
        return None, problems

    axes = {}
    for axis in RELATIONS:
        info = {}
        for key in RELATION_KEYS:
            answers = {name: _relation(sheet, axis, key) for name, sheet in sheets.items()}
            agreed = len(set(answers.values())) == 1
            info[key] = next(iter(answers.values())) if agreed else None
            info[f"{key}_agreed"] = agreed
            info[f"{key}_answers"] = answers
        # 라벨러 중 한 명이라도 실제 관계와 시트 기준 관계를 다르게 봤으면 추출 공백으로 표시한다.
        info["extraction_gap"] = any(info["relation_answers"][n] != info["relation_from_sheet_answers"][n]
                                     for n in sheets)
        axes[axis] = info

    actual, from_sheet = _combine(routes), _combine(sheet_routes)
    merged = {
        "version": 2,
        "axes": axes,
        "routes_by_labeler": routes,
        "routes_from_sheet_by_labeler": sheet_routes,
        "intuition_by_labeler": intuitions,
        **actual,
        "from_sheet": from_sheet,
        # 시트 기준 경로가 실제 경로와 다르면, 모델이 시트를 완벽히 읽어도 틀릴 수 있는 샘플이다.
        "route_changed_by_extraction": from_sheet["acceptable_routes"] != actual["acceptable_routes"],
        "intuition_mismatch": sorted(n for n in routes if routes[n] != intuitions[n]),
        "needs_element_labels": any(route in COMPARABLE_ROUTES for route in actual["acceptable_routes"]),
    }
    return merged, []


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def template(sample: str, labelers: list[str]) -> None:
    folder = SAMPLES_DIR / sample
    my, prior = load(folder / "my_paper.json"), load(folder / "prior_paper.json")
    ids = assign_ids(my, prior)

    lines = [f"# {sample} 라벨 시트", "",
             f"- 내 논문: {first(my, 'title')}",
             f"- 기존 논문: {first(prior, 'title')}", "", GUIDE, ROUTE_GUIDE]
    for heading, paper, fields in (("내 논문", my, ("problem", "contributions", "experiment_results")),
                                   ("기존 논문", prior, ("problem", "limitations", "experiment_results"))):
        for field in fields:
            lines += [f"## {heading} {field}", ""]
            lines += [f"- {text}" for text in as_list(paper.get(field))] or ["- (추출되지 않음)"]
            lines.append("")
    lines += ["## 내 논문 요소 (M)", ""]
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
    for name in labelers:
        path = folder / f"route_{name}.json"
        if path.exists():
            print(f"  [유지] {path.name} 가 이미 있어 덮어쓰지 않았습니다.")
            continue
        path.write_text(json.dumps(_blank_route_sheet(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [생성] {path.relative_to(ROOT)}")
    print(f"  [생성] {(folder / 'label_sheet.md').relative_to(ROOT)}  (M {len(ids['M'])}개, P {len(ids['P'])}개)")


def _verdict(entry) -> str:
    value = entry.get("verdict") if isinstance(entry, dict) else entry
    return value.strip() if isinstance(value, str) else ""


def merge_route_files(folder: Path, minimum: int = 2) -> dict | None:
    files = sorted(f for f in folder.glob("route_*.json") if f.stem != "route_label" and _filled(f))
    if len(files) < minimum:
        return None
    sheets = {f.stem.removeprefix("route_"): load(f) for f in files}
    merged, problems = merge_routes(sheets)
    if problems:
        print("경로 라벨에 비었거나 허용값이 아닌 칸이 있어 합치지 않았습니다.")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    (folder / "route_label.json").write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [생성] {(folder / 'route_label.json').relative_to(ROOT)}")
    for axis, info in merged["axes"].items():
        if not info["relation_agreed"]:
            print(f"  축 의견 갈림  {AXIS_LABELS[axis]}: "
                  + ", ".join(f"{n} {v}" for n, v in info["relation_answers"].items()))
        if info["extraction_gap"]:
            print(f"  추출 공백  {AXIS_LABELS[axis]}: 실제 관계와 시트 기준 관계가 다름")
    if merged["route_changed_by_extraction"]:
        print(f"  시트 기준 경로 {merged['from_sheet']['acceptable_routes']} ≠ 실제 경로 {merged['acceptable_routes']}"
              " → 추출 단계 때문에 경로가 바뀌는 샘플")
    if merged["disputed"]:
        print(f"  경로 갈림 → 허용 경로 {merged['acceptable_routes']} (평가에서 별도 집계)")
    else:
        print(f"  정답 경로: {merged['expected_route']} ({ROUTE_LABELS[merged['expected_route']]})")
    for name in merged["intuition_mismatch"]:
        print(f"  규칙 점검 필요  {name}: 계산 {merged['routes_by_labeler'][name]} ≠ 직감 {merged['intuition_by_labeler'][name]}")
    if not merged["needs_element_labels"]:
        print("  비교가 진행되지 않는 경로라 요소(M) 라벨은 필요 없습니다.")
    return merged


def _filled(path: Path) -> bool:
    """빈 양식(판정 칸이 모두 빈 파일)은 라벨러 수에 넣지 않는다."""
    data = load(path)
    if path.name.startswith("route_"):
        return any(_relation(data, axis) for axis in RELATIONS)
    return any(_verdict(entry) for entry in data.values())


def write_status(folder: Path, provisional: bool) -> None:
    labelers = sorted({f.stem.split("_", 1)[1]
                       for f in [*folder.glob("route_*.json"), *folder.glob("labels_*.json")]
                       if f.stem != "route_label" and _filled(f)})
    status = {"provisional": provisional, "labelers": labelers,
              "note": ("라벨러가 두 명 미만인 임시 라벨이다. 사람 라벨 두 개가 모이면 merge 를 다시 실행한다."
                       if provisional else "라벨러 두 명 이상의 라벨을 합친 정답이다.")}
    (folder / "label_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [생성] {(folder / 'label_status.json').relative_to(ROOT)}  provisional={provisional} {labelers}")


def merge(sample: str, provisional: bool = False) -> None:
    folder = SAMPLES_DIR / sample
    minimum = 1 if provisional else 2
    for path in folder.glob("*_*.json"):
        if path.stem.startswith(("route_", "labels_")) and path.stem != "route_label" and not _filled(path):
            print(f"  [제외] {path.name}: 아직 채우지 않은 양식")
    route_files = [f for f in folder.glob("route_*.json") if f.stem != "route_label" and _filled(f)]
    label_files = sorted(f for f in folder.glob("labels_*.json") if _filled(f))
    route = merge_route_files(folder, minimum) if len(route_files) >= minimum else None
    if len(label_files) < minimum:
        if route is None:
            print(f"채운 route_<이름>.json 또는 labels_<이름>.json 이 {minimum}개 이상 있어야 합칠 수 있습니다."
                  + ("" if provisional else " 한 명뿐이면 --provisional 을 붙이세요."))
            sys.exit(1)
        if route["needs_element_labels"]:
            print(f"  [대기] 요소 라벨(labels_<이름>.json)이 {minimum}개 이상 모이면 다시 merge 하세요.")
    else:
        merge_elements(folder, label_files)
    write_status(folder, provisional)


def merge_elements(folder: Path, files: list[Path]) -> None:
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
    if len(sheets) < 2:
        print("  라벨러 1명: 일치율을 계산하지 않습니다 (임시 라벨)")
    else:
        print(f"  라벨러 일치 {agree}/{len(m_ids)}개 ({agree / len(m_ids):.0%})")
    for d in disagreements:
        print(f"  의견 갈림 → 확인필요  {d}")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "template":
        template(sys.argv[2], sys.argv[3:])
    elif len(sys.argv) in (3, 4) and sys.argv[1] == "merge":
        if len(sys.argv) == 4 and sys.argv[3] != "--provisional":
            print(__doc__)
            sys.exit(1)
        merge(sys.argv[2], provisional=len(sys.argv) == 4)
    else:
        print(__doc__)
        sys.exit(1)
