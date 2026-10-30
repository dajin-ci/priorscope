"""run_storage 보관·삭제 규칙 테스트 (Studio 호출 없음)."""

from datetime import datetime, timedelta

import run_storage as rs


def _make_run(runs, when):
    path = runs / f"{when:%Y%m%d-%H%M%S}-abc123"
    path.mkdir(parents=True)
    (path / "My_Paper.pdf").write_bytes(b"pdf")
    return path


def test_old_run_is_removed_and_recent_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_RETENTION_HOURS", "24")
    now = datetime(2026, 10, 30, 12, 0, 0)
    old = _make_run(tmp_path, now - timedelta(hours=25))
    recent = _make_run(tmp_path, now - timedelta(hours=1))
    removed = rs.cleanup_old_runs(tmp_path, now=now.timestamp())
    assert removed == [old.name]
    assert not old.exists() and recent.exists()


def test_retention_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_RETENTION_HOURS", "1")
    now = datetime(2026, 10, 30, 12, 0, 0)
    run = _make_run(tmp_path, now - timedelta(hours=2))
    rs.cleanup_old_runs(tmp_path, now=now.timestamp())
    assert not run.exists()


def test_invalid_retention_falls_back_to_24(monkeypatch):
    monkeypatch.setenv("RUN_RETENTION_HOURS", "abc")
    assert rs.retention_hours() == 24.0
    monkeypatch.setenv("RUN_RETENTION_HOURS", "-5")
    assert rs.retention_hours() == 24.0


def test_non_run_folders_are_never_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_RETENTION_HOURS", "1")
    other = tmp_path / "keep_me"
    other.mkdir()
    rs.cleanup_old_runs(tmp_path, now=datetime(2030, 1, 1).timestamp())
    assert other.exists()


def test_delete_run_only_inside_runs(tmp_path):
    runs = tmp_path / "runs"
    run = _make_run(runs, datetime(2026, 10, 30, 12, 0, 0))
    outside = tmp_path / "20261030-120000-abc123"
    outside.mkdir()
    assert rs.delete_run(outside, runs) is False and outside.exists()
    assert rs.delete_run(runs / ".." / run.parent.name / run.name, runs) is True
    assert not run.exists()
