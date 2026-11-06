"""
run_storage.py

실행 폴더(runs/<run_id>/) 생성·보관·삭제 (멘토링 10/27 #2 기밀성)

- 실행 폴더에는 미공개 논문 PDF와 분석 결과가 들어 있다.
- 보관 기간(RUN_RETENTION_HOURS, 기본 24시간)이 지난 폴더는 자동 삭제한다.
  Railway에는 예약 작업이 없으므로, 화면이 열리거나 분석을 시작할 때 정리한다.
- 사용자는 결과 화면에서 자기 실행 폴더를 바로 지울 수 있다.
- 무거운 의존성(Studio, ReportLab 등)이 없어 화면에서 바로 import 해도 된다.

새로고침 유지·중복 실행 방지 (멘토링 11/05)
- 화면은 URL의 ?run=<run_id> 로 실행 폴더를 다시 찾는다 (run_dir_from_id).
- 진행 상태는 state.json, 실행 중 표시는 run.lock 으로 남긴다.
  화면이 새로고침되어도 이 두 파일만 읽으면 업로드 파일·진행 단계·결과를 복원할 수 있다.
"""

import hashlib
import json
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
    """보관 기간이 지난 실행 폴더를 지우고, 지운 run_id 목록을 돌려준다. 실행 중인 폴더는 건너뛴다."""
    if not runs_dir.exists():
        return []
    now = time.time() if now is None else now
    limit = retention_hours() * 3600
    removed = []
    for path in runs_dir.iterdir():
        if not _is_run_dir(path, runs_dir):
            continue
        if is_running(path):
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


##################################################
# 새로고침 복원: run_id → 폴더
##################################################

def run_dir_from_id(run_id, runs_dir: Path = RUNS_DIR) -> Path | None:
    """URL에서 온 run_id를 실행 폴더로 바꾼다. 형식이 틀리거나 폴더가 없으면 None (경로 조작 방지)."""
    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        return None
    path = runs_dir / run_id
    return path if _is_run_dir(path, runs_dir) else None


##################################################
# 진행 상태 (state.json)
##################################################

STATE_FILE = "state.json"

# 업로드 파일이 바뀌면 지우는 결과 파일. 예전 결과가 지금 결과처럼 보이지 않게 한다.
RESULT_FILES = (
    "my_paper.json", "prior_paper.json", "suitability.json", "Compare_Input.pdf",
    "compare_result_runs.json", "compare_result.json", "similarity.json", "embedding_cache.json",
    "validated_result.json", "report.json", "insight_result.json",
)
UPLOAD_NAMES = {"my": "My_Paper.pdf", "prior": "Prior_Paper.pdf"}


def read_state(run_dir) -> dict:
    try:
        return json.loads((Path(run_dir) / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "idle", "files": {}}


def write_state(run_dir, state: dict) -> None:
    # 임시 파일에 쓰고 교체한다. 화면이 반쯤 쓴 파일을 읽지 않게 한다.
    path = Path(run_dir) / STATE_FILE
    tmp = path.with_name(f"{STATE_FILE}.{os.getpid()}.{secrets.token_hex(2)}.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def update_state(run_dir, **changes) -> dict:
    state = read_state(run_dir)
    state.update(changes)
    write_state(run_dir, state)
    return state


def count_pages(path) -> int | None:
    try:
        from pypdf import PdfReader
        return len(PdfReader(str(path)).pages)
    except Exception:  # noqa: BLE001  pypdf 미설치·암호화·손상 PDF
        return None


def save_upload(run_dir, kind: str, filename: str, data: bytes) -> dict:
    """업로드한 PDF를 실행 폴더에 저장하고, 이전 결과 파일을 지운다."""
    if kind not in UPLOAD_NAMES:
        raise ValueError(f"kind는 my 또는 prior: {kind!r}")
    run_dir = Path(run_dir)
    path = run_dir / UPLOAD_NAMES[kind]
    path.write_bytes(data)
    for name in RESULT_FILES:
        (run_dir / name).unlink(missing_ok=True)
    info = {"name": filename, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "pages": count_pages(path)}
    state = read_state(run_dir)
    state.setdefault("files", {})[kind] = info
    state.update(status="idle", step=None, error=None)
    write_state(run_dir, state)
    return info


##################################################
# 실행 중 표시 (run.lock)
##################################################

LOCK_FILE = "run.lock"

# 이 시간보다 오래 갱신되지 않은 lock은 서버가 죽고 남은 것으로 본다.
# 실행 쪽이 단계마다 touch_lock()으로 갱신하므로 한 단계만 이 시간을 넘지 않으면 된다.
LOCK_STALE_SECONDS = 20 * 60


def _lock_is_stale(path: Path) -> bool:
    try:
        return time.time() - path.stat().st_mtime > LOCK_STALE_SECONDS
    except OSError:
        return False


def acquire_lock(run_dir) -> bool:
    """lock을 잡으면 True. 이미 실행 중이면 False (버튼을 빠르게 두 번 눌러도 한 번만 실행)."""
    path = Path(run_dir) / LOCK_FILE
    if _lock_is_stale(path):
        path.unlink(missing_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        f.write(str(os.getpid()))
    return True


def touch_lock(run_dir) -> None:
    path = Path(run_dir) / LOCK_FILE
    if path.exists():
        os.utime(path)


def release_lock(run_dir) -> None:
    (Path(run_dir) / LOCK_FILE).unlink(missing_ok=True)


def is_running(run_dir) -> bool:
    path = Path(run_dir) / LOCK_FILE
    return path.exists() and not _lock_is_stale(path)


##################################################
# 새로고침 복원: 결과 파일 → 화면용 bundle
##################################################

BUNDLE_FILES = {
    "my_paper": "my_paper.json",
    "prior_paper": "prior_paper.json",
    "suitability": "suitability.json",
    "compare_result": "compare_result.json",
    "verified": "validated_result.json",
    "report": "report.json",
    "insight": "insight_result.json",
}


def load_bundle(run_dir) -> dict | None:
    """실행 폴더의 결과 파일로 화면용 bundle을 다시 만든다. 추출·적합성 결과가 없으면 None."""
    run_dir = Path(run_dir)
    bundle = {"run_dir": str(run_dir)}
    for key, name in BUNDLE_FILES.items():
        path = run_dir / name
        try:
            bundle[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        except ValueError:
            bundle[key] = None
    if bundle["my_paper"] is None or bundle["prior_paper"] is None or bundle["suitability"] is None:
        return None
    return bundle
