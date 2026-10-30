"""
run_storage.py

실행 폴더(runs/<run_id>/) 생성·보관·삭제 (멘토링 10/27 #2 기밀성)

- 실행 폴더에는 미공개 논문 PDF와 분석 결과가 들어 있다.
- 보관 기간(RUN_RETENTION_HOURS, 기본 24시간)이 지난 폴더는 자동 삭제한다.
  Railway에는 예약 작업이 없으므로, 화면이 열리거나 분석을 시작할 때 정리한다.
- 사용자는 결과 화면에서 자기 실행 폴더를 바로 지울 수 있다.
- 무거운 의존성(Studio, ReportLab 등)이 없어 화면에서 바로 import 해도 된다.
"""

import os
import re
import secrets
import shutil
import time
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path(__file__).resolve().parent / "runs"

# run_id 형식: YYYYMMDD-HHMMSS-<6자리 hex>. 이 형식의 폴더만 지운다.
RUN_ID_PATTERN = re.compile(r"^(\d{8}-\d{6})-[0-9a-f]{6}$")


def retention_hours() -> float:
    """보관 시간. .env 의 RUN_RETENTION_HOURS 로 바꾼다. 잘못된 값이면 기본 24."""
    try:
        hours = float(os.getenv("RUN_RETENTION_HOURS", "24"))
    except ValueError:
        return 24.0
    return hours if hours > 0 else 24.0


def new_run_dir(runs_dir: Path = RUNS_DIR) -> Path:
    run_id = f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _is_run_dir(path: Path, runs_dir: Path) -> bool:
    """runs/ 바로 아래에 있고 run_id 형식인 폴더인지. 다른 경로는 절대 지우지 않는다."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return (
        resolved.parent == runs_dir.resolve()
        and resolved.is_dir()
        and RUN_ID_PATTERN.fullmatch(resolved.name) is not None
    )


def _created_at(path: Path) -> float:
    """run_id의 시각을 쓰고, 읽을 수 없으면 폴더 수정 시각을 쓴다."""
    match = RUN_ID_PATTERN.fullmatch(path.name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d-%H%M%S").timestamp()
        except ValueError:
            pass
    return path.stat().st_mtime


def cleanup_old_runs(runs_dir: Path = RUNS_DIR, now: float | None = None) -> list[str]:
    """보관 기간이 지난 실행 폴더를 지우고, 지운 run_id 목록을 돌려준다."""
    if not runs_dir.exists():
        return []
    now = time.time() if now is None else now
    limit = retention_hours() * 3600
    removed = []
    for path in runs_dir.iterdir():
        if not _is_run_dir(path, runs_dir):
            continue
        try:
            if now - _created_at(path) >= limit:
                shutil.rmtree(path)
                removed.append(path.name)
        except OSError:
            continue  # 동시에 다른 요청이 지운 경우 등. 다음 정리 때 다시 시도한다.
    return removed


def delete_run(run_dir: str | Path, runs_dir: Path = RUNS_DIR) -> bool:
    """사용자가 요청한 실행 폴더 하나를 지운다. 지웠으면 True."""
    path = Path(run_dir)
    if not _is_run_dir(path, runs_dir):
        return False
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()
