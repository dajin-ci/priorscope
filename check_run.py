"""
check_run.py

PriorScope 결과 파일 5개가 '같은 실행에서 나온 짝'인지, 코드가 최신인지 한 번에 점검한다.
Studio를 호출하지 않는다.

사용법 (프로젝트 폴더에서):
    python check_run.py
    python check_run.py --log "유사 기준 v2 지시문"   # 점검 후 runs_log.csv 에 한 줄 기록
"""

import argparse
import csv
import hashlib
import inspect
import json
import os
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

SIMILARITY = BASE / "result" / "similarity.json"
RUNS_LOG = BASE / "runs_log.csv"

parser = argparse.ArgumentParser()
parser.add_argument("--log", metavar="메모", help="점검 후 runs_log.csv 에 이번 실행을 기록")
ARGS = parser.parse_args()

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

if hasattr(validator, "_apply_similarity") and hasattr(validator, "derive_weaknesses"):
    ok("validator.py 최신 (약점 리포트 + 임베딩 유사도 교차 검증 포함)")
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
sim = load(SIMILARITY) if SIMILARITY.exists() else None
if sim is not None:
    if sim.get("m_ids") == [x["id"] for x in ids["M"]] and sim.get("p_ids") == [x["id"] for x in ids["P"]]:
        ok("similarity.json 번호가 지금 논문 JSON과 맞습니다.")
    else:
        bad("similarity.json 이 다른 실행의 결과입니다. python similarity.py 를 다시 실행하세요.")
fresh = validator.validate(my, prior, cmp_, similarity=sim)
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
sim_info = fresh.get("similarity") or {}
if sim_info.get("available"):
    th = sim_info.get("threshold")
    print(f"         임베딩 유사도 {sim_info.get('model')} | 임계값 {th if th is not None else '미정(보고만)'} | 강등 {sim_info.get('demoted') or '없음'}")
else:
    print("         임베딩 유사도 없음 (python similarity.py 로 계산)")

# ------------------------------------------------------------
print("\n" + "=" * 60)
if problems:
    print(f"문제 {len(problems)}건. 위 [문제] 줄을 확인하세요.")
else:
    print("모든 파일이 같은 실행의 짝이고 코드도 최신입니다.")
print("=" * 60 + "\n")


# ------------------------------------------------------------
# 실행 기록 (멘토링 10/27 #7: 지시문 버전 · Config ID · 결과를 함께 남긴다)
# ------------------------------------------------------------
def _agent_config_hash():
    # agent_configs/*.json 내용 해시. 지시문을 바꾸고 다시 내보내면 값이 바뀐다.
    files = sorted((BASE / "agent_configs").glob("*.json"))
    if not files:
        return "-"
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:10]


if ARGS.log is not None:
    try:
        from dotenv import load_dotenv

        load_dotenv(BASE / ".env")
    except ImportError:
        pass
    cov = fresh["coverage"]
    counts = cov["verdict_counts"]
    row = {
        "기록시각": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "메모": ARGS.log,
        "점검": "통과" if not problems else f"문제 {len(problems)}건",
        "MyConfig": os.getenv("MY_PAPER_CONFIG_ID", ""),
        "PriorConfig": os.getenv("PRIOR_PAPER_CONFIG_ID", ""),
        "CompareConfig": os.getenv("COMPARE_CONFIG_ID", ""),
        "지시문해시": _agent_config_hash(),
        "M": len(ids["M"]),
        "P": len(ids["P"]),
        "R-M": len(ids["RM"]),
        "R-P": len(ids["RP"]),
        "일치": counts["일치"],
        "유사": counts["유사"],
        "없음": counts["없음"],
        "확인필요": counts["확인필요"],
        "커버리지": f"{cov['min']}~{cov['max']}",
        "등급": fresh["final_level"],
        "에이전트등급": fresh["classify_level"],
        "유사도임계값": (fresh.get("similarity") or {}).get("threshold"),
        "유사도강등": " ".join((fresh.get("similarity") or {}).get("demoted") or []),
        "status": fresh["status"],
    }
    is_new = not RUNS_LOG.exists()
    with open(RUNS_LOG, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if is_new:
            writer.writeheader()
        writer.writerow(row)
    print(f"실행 기록 추가: {RUNS_LOG.relative_to(BASE)}  ({row['메모']})\n")
