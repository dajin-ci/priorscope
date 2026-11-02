"""서비스 분기, 저장 파일, CLI와 화면 표시 정책을 검증한다 (API는 대체)."""
import importlib
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

from comparison_report import apply_scope_policy, build_report
from suitability import deferred_assessment, normalize_assessment
from test_suitability import PAPER, assessment, verified


@pytest.fixture
def service_module(monkeypatch, tmp_path):
    import config
    # API가 없는 CI에서도 AgentClient 초기화가 가능하게 한다. 실제 호출은 모두 대체한다.
    monkeypatch.setattr(config, "UPSTAGE_API_KEY", "test-not-a-real-key")
    svc = importlib.import_module("service")
    monkeypatch.setattr(svc, "validate_config", lambda: None)
    monkeypatch.setattr(svc, "cleanup_old_runs", lambda: None)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.setattr(svc, "new_run_dir", lambda: run_dir)
    monkeypatch.setattr(svc, "upload_file", Mock(return_value="file-test"))
    monkeypatch.setattr(svc, "analyze_resume", Mock(return_value=PAPER))
    monkeypatch.setattr(svc, "analyze_jd", Mock(return_value=PAPER))
    return svc, run_dir


@pytest.mark.parametrize("route", ["unsuitable", "insufficient"])
def test_blocked_routes_never_build_compare_or_request_similarity(service_module, monkeypatch, route):
    svc, run_dir = service_module
    gate = (normalize_assessment(assessment("different", "different", "generic_only"), PAPER, PAPER)
            if route == "unsuitable" else deferred_assessment("정보 부족"))
    monkeypatch.setattr(svc, "assess_suitability", lambda *args: gate)
    downstream = {}
    for name in ("create_compare_input", "analyze_matching", "UpstageEmbedder", "compute_similarity", "validate"):
        downstream[name] = Mock(side_effect=AssertionError("후속 단계 호출 금지"))
        monkeypatch.setattr(svc, name, downstream[name])
    bundle = svc.run_compare_service(b"my pdf", b"prior pdf")
    assert bundle["verified"] is None and bundle["compare_result"] is None
    assert json.loads((run_dir / "report.json").read_text(encoding="utf-8"))["route"] == route
    assert (run_dir / "suitability.json").exists()
    assert not (run_dir / "Compare_Input.pdf").exists()
    for mock in downstream.values():
        mock.assert_not_called()


@pytest.mark.parametrize("problem,scope,method,route", [
    ("same", "comparable", "different", "research"),
    ("same", "partial", "different", "partial"),
    ("different", "different", "specific_shared", "method"),
])
def test_allowed_routes_propagate_scope_to_pdf_report_and_verified(service_module, monkeypatch,
                                                                 problem, scope, method, route):
    svc, run_dir = service_module
    gate = normalize_assessment(assessment(problem, scope, method), PAPER, PAPER)
    monkeypatch.setattr(svc, "assess_suitability", lambda *args: gate)
    builder = Mock(side_effect=lambda a, b, path, font, **kwargs: path.write_bytes(b"pdf"))
    monkeypatch.setattr(svc, "create_compare_input", builder)
    monkeypatch.setattr(svc, "analyze_matching", Mock(return_value={}))
    monkeypatch.setattr(svc, "UpstageEmbedder", Mock())
    monkeypatch.setattr(svc, "compute_similarity", Mock(return_value={"matrix": {}}))
    monkeypatch.setattr(svc, "validate", Mock(return_value=verified()))
    steps = []
    bundle = svc.run_compare_service(b"my pdf", b"prior pdf", on_step=steps.append)
    assert builder.call_args.kwargs["suitability"]["route"] == route
    assert steps.index("3단계 · 비교 적합성 판단") < steps.index("4단계 · 비교용 PDF 생성")
    assert bundle["report"]["route"] == route and steps[-1] == "완료"
    saved = json.loads((run_dir / "validated_result.json").read_text(encoding="utf-8"))
    assert saved["overall_assessment_applicable"] == (route == "research")
    if route == "method":
        assert saved["numeric_checks"] == []
    assert (run_dir / "report.json").exists()


def test_same_file_is_rejected_before_any_api(service_module):
    svc, _ = service_module
    with pytest.raises(svc.StepError, match="같은 파일"):
        svc.run_compare_service(b"same", b"same")
    svc.analyze_resume.assert_not_called()


@pytest.fixture
def view(monkeypatch):
    import streamlit_app as ui
    st = MagicMock()
    monkeypatch.setattr(ui, "st", st)
    renderers = {}
    for name in ("render_badges", "render_mapping_table", "render_novel_overlap",
                 "render_weakness", "render_numeric", "render_uncertain", "render_report"):
        renderers[name] = Mock()
        monkeypatch.setattr(ui, name, renderers[name])
    return ui, st, renderers


@pytest.mark.parametrize("problem,scope,method,grade,numeric", [
    ("same", "comparable", "specific_shared", True, True),
    ("same", "partial", "different", False, True),
    ("different", "different", "specific_shared", False, False),
])
def test_view_only_renders_sections_allowed_by_scope(view, problem, scope, method, grade, numeric):
    ui, st, renderers = view
    gate = normalize_assessment(assessment(problem, scope, method), PAPER, PAPER)
    out = verified()
    out.update({"mappings": [], "uncertain_items": [], "issues": [], "numeric_checks": []})
    out = apply_scope_policy(out, gate)
    bundle = {"my_paper": PAPER, "prior_paper": PAPER, "suitability": gate, "verified": out,
              "compare_result": {}, "report": build_report(gate, out)}
    ui.render_result(bundle, "test")
    assert renderers["render_badges"].called == grade
    assert renderers["render_novel_overlap"].called == grade
    assert renderers["render_weakness"].called == grade
    assert renderers["render_mapping_table"].called
    assert renderers["render_numeric"].called == numeric
    assert st.subheader.call_args_list[0].args == (gate["label"],)
    saved = json.loads(st.download_button.call_args_list[0].args[1])
    assert saved["report"]["route"] == gate["route"]


def test_blocked_and_legacy_views_do_not_show_novelty_or_grade(view):
    ui, st, renderers = view
    gate = deferred_assessment("정보가 부족합니다")
    bundle = {"my_paper": PAPER, "prior_paper": PAPER, "suitability": gate, "verified": None,
              "compare_result": None}
    ui.render_result(bundle, "test")
    for renderer in renderers.values():
        renderer.assert_not_called()
    del bundle["suitability"]
    ui.render_result(bundle, "legacy")
    assert any("도입 전" in call.args[0] for call in st.warning.call_args_list)
    for renderer in renderers.values():
        renderer.assert_not_called()


def test_cli_uses_the_same_service(monkeypatch, capsys):
    import app
    fake = Mock(return_value={"report": {"title": "비교 부적합 안내", "summary": "비교 생략"},
                              "run_dir": "runs/test"})
    monkeypatch.setattr(app, "run_compare_service", fake)
    monkeypatch.setattr(app, "RESUME_FILE", Mock(read_bytes=Mock(return_value=b"my")))
    monkeypatch.setattr(app, "JD_FILE", Mock(read_bytes=Mock(return_value=b"prior")))
    assert app.main() == 0
    fake.assert_called_once_with(b"my", b"prior", on_step=print)
    assert "비교 부적합 안내" in capsys.readouterr().out


def test_scoped_pdf_is_generated_with_shared_ids(tmp_path, monkeypatch):
    import compare_builder
    from ids import assign_ids
    gate = normalize_assessment(assessment("different", "different"), PAPER, PAPER)
    calls = []
    original = compare_builder.add_text
    def capture(story, text):
        calls.append(text)
        return original(story, text)
    monkeypatch.setattr(compare_builder, "add_text", capture)
    path = tmp_path / "compare.pdf"
    ids = compare_builder.create_compare_input(PAPER, PAPER, path, suitability=gate)
    assert ids == assign_ids(PAPER, PAPER)
    assert path.read_bytes().startswith(b"%PDF")
    assert any("성능 우위를 주장하지" in text for text in calls)


def test_checker_accepts_blocked_run_without_old_compare_files(tmp_path):
    import os
    import subprocess
    import sys
    gate = deferred_assessment("정보 부족")
    (tmp_path / "suitability.json").write_text(json.dumps(gate), encoding="utf-8")
    (tmp_path / "report.json").write_text(json.dumps(build_report(gate)), encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    out = subprocess.run([sys.executable, str(root / "check_run.py"), "--run-dir", str(tmp_path)],
                         capture_output=True, text=True, encoding="utf-8",
                         env={**os.environ, "PYTHONUTF8": "1"}, timeout=20)
    assert out.returncode == 0, out.stderr
    assert "후속 분석 생략: True" in out.stdout
