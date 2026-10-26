"""
check_run.py

PriorScope 결과 파일 5개가 '같은 실행에서 나온 짝'인지, 코드가 최신인지 한 번에 점검한다.
Studio를 호출하지 않는다.

사용법 (프로젝트 폴더에서):
    python check_run.py
"""

import inspect
import json
import re
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
FILES = {
    "my_paper": BASE / "output" / "my_paper.json",
    "prior_paper": BASE / "output" / "prior_paper.json",
    "compare_input": BASE / "output" / "Compare_Input.pdf",
    "compare_result": BASE / "result" / "compare_result.json",
    "validated": BASE / "result" / "validated_result.json",
}

problems = []


def ok(msg):
    print(f"  [OK]   {msg}")


def bad(msg):
    print(f"  [문제] {msg}")
    problems.append(msg)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------
print("\n1. 코드 버전")
# ------------------------------------------------------------
import validator  # noqa: E402
import compare_builder  # noqa: E402

if hasattr(validator, "_canon_metric") and "NO_MATCH_SCOPE_UNKNOWN" in inspect.getsource(validator):
    ok("validator.py 최신 (지표 정규화 + 검토 범위 검사 포함)")
else:
    bad("validator.py가 예전 버전입니다. 새 파일로 교체하세요.")

if "font_path" in inspect.signature(compare_builder.create_compare_input).parameters:
    ok("compare_builder.py 최신")
else:
    bad("compare_builder.py가 예전 버전입니다. 새 파일로 교체하세요.")

# ------------------------------------------------------------
print("\n2. 파일 존재와 생성 순서")
# ------------------------------------------------------------
missing = [name for name, path in FILES.items() if not path.exists()]
if missing:
    for name in missing:
        bad(f"{FILES[name].relative_to(BASE)} 가 없습니다.")
    print("\n결과 파일이 없어 점검을 멈춥니다. python app.py 를 먼저 실행하세요.")
    raise SystemExit(1)

times = {name: path.stat().st_mtime for name, path in FILES.items()}
for name, path in FILES.items():
    stamp = datetime.fromtimestamp(times[name]).strftime("%m-%d %H:%M")
    print(f"         {stamp}  {path.relative_to(BASE)}")

order = [
    ("my_paper", "compare_input"),
    ("prior_paper", "compare_input"),
    ("compare_input", "compare_result"),
    ("compare_result", "validated"),
]
order_ok = True
for before, after in order:
    if times[before] > times[after] + 1:
        bad(f"{before} 가 {after} 보다 나중에 만들어졌습니다. 순서가 꼬였습니다.")
        order_ok = False
if order_ok:
    ok("생성 순서 정상 (논문 JSON → 비교 PDF → 비교 결과 → 검증 결과)")

# ------------------------------------------------------------
print("\n3. 번호 짝 맞춤 (비교 결과가 지금 논문 JSON 기준인가)")
# ------------------------------------------------------------
from ids import assign_ids  # noqa: E402

my, prior, cmp_ = load(FILES["my_paper"]), load(FILES["prior_paper"]), load(FILES["compare_result"])
ids = assign_ids(my, prior)
m_ids = {x["id"] for x in ids["M"]}
p_count = len(ids["P"])
print(f"         지금 JSON 기준: M {len(m_ids)}개, P {p_count}개, R-M {len(ids['RM'])}개, R-P {len(ids['RP'])}개")

lines = cmp_.get("element_mapping") or []
written_m = {m.group(1) for line in lines if (m := re.match(r"\s*(M\d+)", str(line)))}
referenced_p = set()
for line in lines:
    referenced_p.update(int(n) for n in re.findall(r"P(\d+)", str(line)))

if written_m == m_ids:
    ok(f"비교 결과가 M 요소 {len(m_ids)}개를 모두 다룹니다.")
else:
    bad(f"비교 결과의 M 목록이 다릅니다. 빠짐 {sorted(m_ids - written_m)}, 없는 번호 {sorted(written_m - m_ids)}")

scope_ends = {int(n) for line in lines for n in re.findall(r"검토 범위\s*P\d+\s*[~\-]\s*P?(\d+)", str(line))}
if scope_ends and scope_ends != {p_count}:
    bad(f"'없음' 판정의 검토 범위 끝이 P{sorted(scope_ends)}인데 지금 P는 {p_count}개입니다. 다른 입력으로 만든 비교 결과입니다.")
elif scope_ends:
    ok(f"'없음' 판정의 검토 범위가 P1~P{p_count}로 지금 P 목록과 맞습니다.")

if referenced_p and max(referenced_p) > p_count:
    bad(f"비교 결과가 P{max(referenced_p)}까지 언급하지만 지금 P는 {p_count}개입니다. 예전 비교 결과입니다.")
else:
    ok("비교 결과의 P 번호가 지금 P 목록 범위 안에 있습니다.")

# ------------------------------------------------------------
print("\n4. 검증 결과가 지금 파일로 다시 계산한 값과 같은가")
# ------------------------------------------------------------
saved = load(FILES["validated"])
fresh = validator.validate(my, prior, cmp_)
same = (
    saved.get("final_level") == fresh["final_level"]
    and saved.get("coverage", {}).get("min") == fresh["coverage"]["min"]
    and saved.get("coverage", {}).get("max") == fresh["coverage"]["max"]
    and "result_warnings" in saved
)
if same:
    ok("validated_result.json 이 최신입니다.")
else:
    bad("validated_result.json 이 지금 파일·코드와 다릅니다. 검증만 다시 실행하세요.")

# ------------------------------------------------------------
print("\n5. 현재 결과 요약")
# ------------------------------------------------------------
counts = fresh["coverage"]["verdict_counts"]
print(f"         등급 {fresh['final_level']} | 커버리지 {fresh['coverage']['min']} ~ {fresh['coverage']['max']}%")
print(f"         Classify {fresh['classify_level']} | 교차 검증 {'일치' if fresh['classify_agrees'] else '불일치'}")
print(f"         판정 {counts} | status {fresh['status']}")
print(f"         경고 {json.dumps(fresh['result_warnings'], ensure_ascii=False)}")

# ------------------------------------------------------------
print("\n" + "=" * 60)
if problems:
    print(f"문제 {len(problems)}건. 위 [문제] 줄을 확인하세요.")
else:
    print("모든 파일이 같은 실행의 짝이고 코드도 최신입니다.")
print("=" * 60 + "\n")
