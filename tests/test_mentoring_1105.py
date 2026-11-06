"""멘토링 11/05 반영: 새로고침 복원, 중복 실행 방지, 관심 초점, 관계·인사이트 (Studio 호출 없음)."""
import json
import os
import time
from unittest.mock import Mock

import pytest

import run_storage as rs
from focus import focus_lines, normalize
from test_suitability import PAPER, assessment, verified
from suitability import normalize_assessment


def _run(tmp_path):
    path = tmp_path / "20261106-120000-abc123"
    path.mkdir()
    return path


##################################################
# run_storage: 복원·상태·lock
##################################################

def test_run_dir_from_id_rejects_bad_ids(tmp_path):
    run = _run(tmp_path)
    assert rs.run_dir_from_id(run.name, tmp_path) == run
    for bad in (None, "", "../etc", "20261106-120000-zzzzzz", "20261106-120000-abc124"):
        assert rs.run_dir_from_id(bad, tmp_path) is None


def test_save_upload_records_file_and_clears_old_results(tmp_path):
    run = _run(tmp_path)
    (run / "validated_result.json").write_text("{}")
    (run / "report.json").write_text("{}")
    info = rs.save_upload(run, "my", "mine.pdf", b"%PDF-fake")
    assert (run / "My_Paper.pdf").read_bytes() == b"%PDF-fake"
    assert not (run / "validated_result.json").exists() and not (run / "report.json").exists()
    state = rs.read_state(run)
    assert state["files"]["my"]["name"] == "mine.pdf" == info["name"]
    assert state["status"] == "idle"
    with pytest.raises(ValueError):
        rs.save_upload(run, "other", "x.pdf", b"x")


def test_lock_blocks_second_start_and_stale_lock_is_reclaimed(tmp_path, monkeypatch):
    run = _run(tmp_path)
    assert rs.acquire_lock(run) and rs.is_running(run)
    assert not rs.acquire_lock(run)
    old = time.time() - rs.LOCK_STALE_SECONDS - 5
    os.utime(run / rs.LOCK_FILE, (old, old))
    assert not rs.is_running(run)
    assert rs.acquire_lock(run)
    rs.release_lock(run)
    assert not rs.is_running(run)


def test_cleanup_skips_running_run(tmp_path, monkeypatch):
    monkeypatch.setenv("RUN_RETENTION_HOURS", "1")
    run = tmp_path / "20200101-000000-abc123"
    run.mkdir()
    rs.acquire_lock(run)
    assert rs.cleanup_old_runs(tmp_path) == []
    rs.release_lock(run)
    assert rs.cleanup_old_runs(tmp_path) == [run.name]


def test_load_bundle_needs_extraction_and_suitability(tmp_path):
    run = _run(tmp_path)
    assert rs.load_bundle(run) is None
    for name in ("my_paper.json", "prior_paper.json", "suitability.json"):
        (run / name).write_text(json.dumps({"ok": name}))
    bundle = rs.load_bundle(run)
    assert bundle["suitability"] == {"ok": "suitability.json"} and bundle["verified"] is None


##################################################
# service: 백그라운드 실행
##################################################

@pytest.fixture
def svc(monkeypatch):
    import importlib
    import config
    monkeypatch.setattr(config, "UPSTAGE_API_KEY", "test-not-a-real-key")
    return importlib.import_module("service")


def _wait_done(run, timeout=5):
    end = time.time() + timeout
    # 상태를 먼저 쓰고 lock을 나중에 푼다 (반대면 화면이 '중단됨'으로 오인한다). 둘 다 끝날 때까지 기다린다.
    while time.time() < end and (rs.read_state(run).get("status") == "running" or rs.is_running(run)):
        time.sleep(0.02)
    return rs.read_state(run)


def test_background_run_records_done_and_releases_lock(svc, tmp_path, monkeypatch):
    run = _run(tmp_path)
    rs.save_upload(run, "my", "a.pdf", b"a")
    rs.save_upload(run, "prior", "b.pdf", b"b")
    gate = Mock()

    def fake(my, prior, on_step=None, *, run_dir=None, focus=None):
        on_step("1단계 · 내 논문 분석")
        gate.wait = True
        time.sleep(0.2)
        gate(focus)

    monkeypatch.setattr(svc, "run_compare_service", fake)
    assert svc.start_in_background(run, {"aspects": ["data"]})
    assert not svc.start_in_background(run)  # 진행 중 두 번째 클릭은 무시
    state = _wait_done(run)
    assert state["status"] == "done" and not rs.is_running(run)
    gate.assert_called_once_with({"aspects": ["data"]})


def test_background_failure_keeps_step_and_message(svc, tmp_path, monkeypatch):
    run = _run(tmp_path)
    rs.save_upload(run, "my", "a.pdf", b"a")
    rs.save_upload(run, "prior", "b.pdf", b"b")

    def fail(*args, **kwargs):
        raise svc.StepError("2단계 · 기존 논문 분석", "시간 초과")

    monkeypatch.setattr(svc, "run_compare_service", fail)
    assert svc.start_in_background(run)
    state = _wait_done(run)
    assert state["status"] == "failed"
    assert state["error"] == {"step": "2단계 · 기존 논문 분석", "message": "시간 초과"}
    assert not rs.is_running(run)


def _allowed_pipeline(svc, monkeypatch):
    gate = normalize_assessment(assessment("same", "comparable", "specific_shared"), PAPER, PAPER)
    monkeypatch.setattr(svc, "assess_suitability", lambda *args: gate)
    builder = Mock(side_effect=lambda a, b, path, font, **k: path.write_bytes(b"pdf"))
    monkeypatch.setattr(svc, "create_compare_input", builder)
    monkeypatch.setattr(svc, "upload_file", Mock(return_value="file"))
    monkeypatch.setattr(svc, "analyze_matching", Mock(return_value={}))
    monkeypatch.setattr(svc, "UpstageEmbedder", Mock())
    monkeypatch.setattr(svc, "compute_similarity", Mock(return_value={"matrix": {}}))
    monkeypatch.setattr(svc, "combine_runs", Mock(return_value=verified() | {"consensus": {"representative_run": 1}}))
    return builder


def test_focus_reaches_builder_only_when_given(svc, tmp_path, monkeypatch):
    builder = _allowed_pipeline(svc, monkeypatch)
    svc.run_from_extracted(PAPER, PAPER, tmp_path, compare_runs=1)
    assert "focus" not in builder.call_args.kwargs
    svc.run_from_extracted(PAPER, PAPER, tmp_path, compare_runs=1, focus={"aspects": ["data"]})
    assert builder.call_args.kwargs["focus"] == {"aspects": ["data"]}


def test_insight_failure_does_not_stop_pipeline(svc, tmp_path, monkeypatch):
    _allowed_pipeline(svc, monkeypatch)
    monkeypatch.setattr(svc.insight_agent, "is_enabled", lambda: True)
    monkeypatch.setattr(svc.insight_agent, "run_insight", Mock(side_effect=TimeoutError("느림")))
    steps = []
    bundle = svc.run_from_extracted(PAPER, PAPER, tmp_path, on_step=steps.append, compare_runs=1)
    assert bundle["verified"] is not None and "TimeoutError" in bundle["insight"]["error"]
    assert steps[-1] == "8단계 · 관계·인사이트 분석"
    assert (tmp_path / "insight_result.json").exists()


def test_insight_skipped_when_disabled(svc, tmp_path, monkeypatch):
    _allowed_pipeline(svc, monkeypatch)
    monkeypatch.setattr(svc.insight_agent, "is_enabled", lambda: False)
    bundle = svc.run_from_extracted(PAPER, PAPER, tmp_path, compare_runs=1)
    assert bundle["insight"] is None and not (tmp_path / "insight_result.json").exists()


##################################################
# 관심 초점 · 관계 분석 정리
##################################################

def test_focus_keeps_only_known_keys():
    assert normalize({"aspects": ["data", "hack"], "goals": ["reviewer", 3]}) == {"aspects": ["data"], "goals": ["reviewer"]}
    assert normalize(None) == {"aspects": [], "goals": []}
    assert focus_lines(None) == []
    assert any("리뷰어" in line for line in focus_lines({"goals": ["reviewer"]}))


def test_builder_writes_focus_section(tmp_path, monkeypatch):
    import compare_builder
    texts = []
    original = compare_builder.paragraph
    monkeypatch.setattr(compare_builder, "paragraph", lambda text, *a: texts.append(str(text)) or original(text, *a))
    compare_builder.create_compare_input(PAPER, PAPER, tmp_path / "c.pdf", focus={"aspects": ["efficiency"]})
    assert "사용자 관심 초점" in texts and any("효율성" in t for t in texts)
    assert any("모든 M 요소에 한 줄씩" in t for t in texts)


def test_clean_insight_checks_ids_and_marks_inference():
    import insight_agent
    v = {"mappings": [{"id": "M1", "final_verdict": "유사"}, {"id": "M2", "final_verdict": "확인필요"}]}
    raw = {
        "relations": [
            {"type": "연결", "my_ids": ["M2"], "prior_ids": ["P1"], "insight": "A→C"},
            {"type": "확장", "my_ids": ["M9"], "prior_ids": ["P1"]},
            {"type": "칭찬", "my_ids": ["M1"], "prior_ids": ["P1"]},
        ],
        "overlap_insights": [{"my_id": "M1", "prior_ids": ["P1", "P7"], "delta": ""}, {"my_id": "M2"}],
        "focus_notes": "not a list",
    }
    out = insight_agent.clean_insight(raw, v, ["P1"])
    assert len(out["relations"]) == 1
    rel = out["relations"][0]
    assert rel["inferred"] and rel["uncertain_ids"] == ["M2"]
    assert out["overlap_insights"] == [{"my_id": "M1", "prior_ids": ["P1"], "delta": "확인 필요",
                                        "how_to_write": "", "reviewer_question": ""}]
    assert out["focus_notes"] == [] and len(out["dropped"]) == 3


def test_insight_rejects_blocked_route(monkeypatch):
    import config
    import insight_agent
    monkeypatch.setattr(config, "INSIGHT_MODEL", "m")
    with pytest.raises(ValueError):
        insight_agent.run_insight(PAPER, PAPER, {"mappings": []}, route="unsuitable", client=Mock())


def test_insight_parses_fenced_json_with_fake_client(monkeypatch):
    import config
    import insight_agent
    monkeypatch.setattr(config, "INSIGHT_MODEL", "local-model")
    content = '```json\n{"relations": [], "overlap_insights": [], "focus_notes": ["n"]}\n```'
    client = Mock()
    client.chat.completions.create.return_value = Mock(choices=[Mock(message=Mock(content=content))])
    out = insight_agent.run_insight(PAPER, PAPER, {"mappings": []}, route="partial", client=client)
    assert out["focus_notes"] == ["n"] and out["route"] == "partial"
    prompt = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert prompt.startswith("[비교 경로] partial")

