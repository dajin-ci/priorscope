"""
revalidate.py

저장된 실행 폴더의 AI 출력으로 7단계 코드 검증만 다시 한다. Studio·Solar를 호출하지 않아 크레딧이 들지 않는다.
validator 규칙을 고친 뒤, 이미 끝난 분석에 새 규칙을 적용해 볼 때 쓴다.

    python revalidate.py                 # 가장 최근 실행 폴더
    python revalidate.py runs/<run_id>   # 지정한 실행 폴더

validated_result.json 과 report.json 을 덮어쓴다. 화면을 새로고침하면 새 결과가 보인다.
"""

import json
import sys
from pathlib import Path

from comparison_report import apply_scope_policy, build_report
from run_storage import RUNS_DIR
from validator import combine_runs


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(data, path):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def revalidate(run_dir: Path) -> dict:
    required = ["my_paper.json", "prior_paper.json", "suitability.json", "compare_result_runs.json"]
    missing = [name for name in required if not (run_dir / name).exists()]
    if missing:
        raise SystemExit(f"{run_dir}: 비교 단계까지 끝난 실행이 아닙니다 (없는 파일: {', '.join(missing)})")

    old = _load(run_dir / "validated_result.json") if (run_dir / "validated_result.json").exists() else {}
    similarity = _load(run_dir / "similarity.json") if (run_dir / "similarity.json").exists() else None
    suitability = _load(run_dir / "suitability.json")

    # 실패했던 Compare Agent 실행 기록은 이전 결과에서 그대로 가져온다 (다시 실행하지 않으므로).
    failed_runs = old.get("consensus", {}).get("failed_runs", [])
    verified = combine_runs(_load(run_dir / "my_paper.json"), _load(run_dir / "prior_paper.json"),
                            _load(run_dir / "compare_result_runs.json"), similarity=similarity,
                            failed_runs=failed_runs)
    if old.get("similarity", {}).get("error"):
        verified.setdefault("similarity", {})["error"] = old["similarity"]["error"]
    verified = apply_scope_policy(verified, suitability)
    _save(verified, run_dir / "validated_result.json")
    _save(build_report(suitability, verified), run_dir / "report.json")

    print(f"{run_dir.name}: {old.get('status', '-')} -> {verified['status']}")
    for issue in verified["issues"]:
        if issue["severity"] in ("error", "info"):
            print(f"  [{issue['severity']}] {issue['code']} {issue['path']}")
    return verified


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        dirs = [d for d in RUNS_DIR.iterdir() if d.is_dir()] if RUNS_DIR.exists() else []
        if not dirs:
            raise SystemExit("runs/ 에 실행 폴더가 없습니다.")
        target = max(dirs, key=lambda d: d.stat().st_mtime)
    revalidate(target)
