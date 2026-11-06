"""
streamlit_app.py

PriorScope 결과 화면 (설계서 5장)

탭 1 · 새로 분석      : PDF 2개 → service.run_compare_service() → 결과
탭 2 · 샘플 결과 보기 : samples/ 의 JSON 4개로 같은 화면을 즉시 표시
"""

import hashlib
import json
import os
import time
from pathlib import Path

import streamlit as st

from ids import assign_ids, clean_text
from validator import derive_weaknesses
from suitability import AXIS_LABELS, deferred_assessment
from comparison_report import build_report
from focus import ASPECTS, GOALS, normalize as normalize_focus
from run_storage import (
    cleanup_old_runs, delete_run, is_running, load_bundle, new_run_dir, read_state,
    retention_hours, run_dir_from_id, save_upload, update_state,
)
import insight_agent

BASE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "samples"
UPLOAD_SAMPLES = {"my": "My_Paper.pdf", "prior": "Prior_Paper.pdf"}
SAMPLE_FILES = {
    "my_paper": "my_paper.json",
    "prior_paper": "prior_paper.json",
    "compare_result": "compare_result.json",
    "verified": "validated_result.json",
}

# 페이지 수 안내 기준. bench_pages.py 측정 결과로 정한다 (지금 값은 임시).
PAGE_WARN = int(os.getenv("PAGE_WARN", "20"))
PAGE_MAX = int(os.getenv("PAGE_MAX", "40"))

# service.py 의 on_step 이름과 같아야 진행 표시가 맞는다.
STEP_ORDER = [
    "1단계 · 내 논문 분석", "2단계 · 기존 논문 분석", "3단계 · 비교 적합성 판단",
    "4단계 · 비교용 PDF 생성", "5단계 · 비교 분석", "6단계 · 임베딩 유사도",
    "7단계 · 코드 검증", "8단계 · 관계·인사이트 분석",
]

VERDICT_BADGE = {"일치": "🔴 일치", "유사": "🟠 유사", "없음": "🟢 없음", "확인필요": "🟡 확인필요"}
SHORT_LEVEL = {"High Overlap": "High", "Medium Overlap": "Medium", "Low Overlap": "Low"}

# 넓은 화면의 가독성을 위해 본문 폭을 제한하고, 화면 폭에 맞춰 여백을 조정한다.
PAGE_STYLES = """
<style>
[data-testid="stMainBlockContainer"] {
    box-sizing: border-box;
    width: 100%;
    max-width: 1440px;
    margin-left: auto;
    margin-right: auto;
    padding-left: clamp(1.25rem, 4vw, 4rem);
    padding-right: clamp(1.25rem, 4vw, 4rem);
}
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"] {
        padding-left: 1rem;
        padding-right: 1rem;
    }
}
</style>
"""



##################################################
# Helpers
##################################################

def _first(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    if isinstance(value, list):
        value = value[0] if value else None
    return clean_text(value) if isinstance(value, str) else value


def _list(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    if isinstance(value, list):
        return [clean_text(v) for v in value if str(v).strip()]
    return [clean_text(value)] if value else []


def _level_text(verified):
    """확정이면 등급, 보류면 범위(예: Low~Medium)."""
    if verified["final_level"] != "판정 보류":
        return SHORT_LEVEL.get(verified["final_level"], verified["final_level"]), "확정"

    cov = verified["coverage"]
    if cov["min"] is None:
        return "판정 보류", "보류"

    th = cov["thresholds"]

    def level(p):
        return "High" if p >= th["high"] else "Medium" if p >= th["medium"] else "Low"

    return f"{level(cov['min'])}~{level(cov['max'])}", "보류"


def _hours_text():
    hours = retention_hours()
    return f"{hours:g}시간"


def _input_id(*contents):
    h = hashlib.sha256()
    for c in contents:
        h.update(hashlib.sha256(c).digest())
    return h.hexdigest()


##################################################
# Result sections
##################################################

def render_badges(verified):
    level, status = _level_text(verified)
    cov = verified["coverage"]
    counts = cov["verdict_counts"]

    if cov["min"] is None:
        cov_text = "-"
    elif cov["min"] == cov["max"]:
        cov_text = f"{cov['min']}%"
    else:
        cov_text = f"{cov['min']}~{cov['max']}%"

    classify = SHORT_LEVEL.get(verified.get("classify_level"), verified.get("classify_level") or "-")
    if status == "보류":
        cross = "참고"
    else:
        cross = "일치" if verified["classify_agrees"] else "확인필요"

    c1, c2, c3 = st.columns(3)
    c1.metric(f"최종 등급 ({status})", level, border=True)
    c2.metric("커버리지", cov_text, border=True)
    c3.metric("교차 검증", cross, border=True)
    st.caption(
        f"Classify 등급: {classify} · "
        f"일치 {counts['일치']} · 유사 {counts['유사']} · 없음 {counts['없음']} · 확인필요 {counts['확인필요']}"
    )

    if status == "보류":
        st.warning("확인필요 항목이 결론을 바꿀 수 있어 등급을 확정하지 않았습니다. 아래 '확인 필요 목록'을 확인하세요.")


def render_mapping_table(verified, ids):
    st.subheader("요소 대응표")
    p_text = {p["id"]: p["text"] for p in ids["P"]}
    rows = []
    for m in verified["mappings"]:
        prior = "\n".join(f"{pid}. {p_text.get(pid, '(없는 번호)')}" for pid in m["prior_ids"]) or "-"
        rows.append({
            "M": m["id"],
            "내 요소": m["text"],
            "대응 P 요소": prior,
            "판정": VERDICT_BADGE.get(m["final_verdict"], m["final_verdict"]),
            "근거": clean_text(m["evidence"]),
            "설명": clean_text(m["explanation"]),
            "강등 사유": " / ".join(m["demoted_reasons"]),
            # 반복 실행 결과가 있으면 실행별 판정을 함께 보여 준다 (흔들린 판정은 확인필요로 합쳐짐).
            **({"실행별 판정": " / ".join(m["votes"])} if m.get("votes") and len(m["votes"]) > 1 else {}),
        })
    st.dataframe(rows, hide_index=True)


def render_novel_overlap(verified, ids=None, insight=None):
    novel = [m for m in verified["mappings"] if m["final_verdict"] == "없음"]
    overlap = [m for m in verified["mappings"] if m["final_verdict"] in ("일치", "유사")]
    p_section = {p["id"]: p.get("section") for p in (ids or {}).get("P", [])}
    detail = {o["my_id"]: o for o in (insight or {}).get("overlap_insights", [])}

    left, right = st.columns(2)
    with left:
        st.subheader("비교 논문에서 대응되지 않은 요소 (차별점 후보)")
        if novel:
            for m in novel:
                st.text(f"{m['id']}. {m['text']}")
        else:
            st.info("대응 없음으로 남은 요소가 없습니다.")
    with right:
        st.subheader("기존 연구를 바탕으로 한 요소 (겹침)")
        if overlap:
            st.caption("Related Work에서 인용할 위치와, 겹치는 안에서 내 쪽이 바꾼 점을 함께 적어 두세요.")
            for m in overlap:
                with st.container(border=True):
                    st.text(f"{m['id']} ↔ {','.join(m['prior_ids'])} ({m['final_verdict']}). {m['text']}")
                    sections = sorted({p_section[p] for p in m["prior_ids"] if p_section.get(p)})
                    if sections:
                        st.caption("인용할 위치: " + ", ".join(f"기존 논문 {sec}절" for sec in sections))
                    if m["id"] in detail:
                        d = detail[m["id"]]
                        st.caption(f"내 쪽의 차이: {d['delta']}")
                        if d.get("how_to_write"):
                            st.caption(f"서술 방식: {d['how_to_write']}")
                        if d.get("reviewer_question"):
                            st.caption(f"예상 리뷰어 질문: {d['reviewer_question']}")
        else:
            st.info("겹치는 요소가 없습니다.")


def render_insight(insight):
    """8단계 관계·인사이트. 보조 분석이라 실패해도 다른 결과는 그대로 둔다."""
    if not insight:
        return
    st.subheader("두 논문 주장의 관계")
    if insight.get("error"):
        st.caption(f"관계 분석은 이번에 실패했습니다 ({insight['error']}). 다른 결과는 정상입니다.")
        return
    relations = insight.get("relations") or []
    if not relations:
        st.info("확장·보완·상충·연결로 볼 만한 뚜렷한 관계를 찾지 못했습니다.")
    for r in relations:
        with st.container(border=True):
            st.markdown(f"**{r['type']}** · 내 논문 {', '.join(r['my_ids'])} ↔ 기존 논문 {', '.join(r['prior_ids'])}")
            st.text(f"기존 논문: {r['prior_claim']}")
            st.text(f"내 논문: {r['my_claim']}")
            st.write(r["insight"])
            if r.get("inferred"):
                st.caption("두 논문의 주장을 이은 추론입니다. 직접 검증된 결과가 아닐 수 있으니 본문에서는 가설로 표현하세요.")
            if r.get("uncertain_ids"):
                st.caption(f"{', '.join(r['uncertain_ids'])}는 대응이 확인필요인 요소입니다. 확인한 뒤에 쓰세요.")
    for note in insight.get("focus_notes") or []:
        st.info(note)
    st.caption(f"AI 분석({insight.get('backend') or '-'})이며 번호 검증만 코드가 했습니다. 원문을 확인한 뒤 사용하세요.")


def _fmt_diff(diff, unit):
    return f"{diff:+.4g} {unit or ''}".strip() if isinstance(diff, (int, float)) else "-"


def render_weakness(verified, ids):
    st.subheader("보완을 검토할 지점 (기존 논문 대비)")
    st.caption(
        "코드가 대응표와 정량 비교에서 계산한 항목입니다. "
        "기존 논문에만 있는 구성이 꼭 필요한 것은 아니므로, 내 연구 범위에 넣을지 아니면 범위 밖이라고 밝힐지 정해 보세요."
    )
    # 예전 결과 파일(weaknesses 없음)도 같은 함수로 계산해 보여준다.
    weak = verified.get("weaknesses") or derive_weaknesses(verified, ids)

    st.markdown(f"**기존 논문에만 있는 요소** · {weak['counts']['prior_only']}개")
    if not weak["prior_only_complete"]:
        st.warning(
            "대응 판정이 빠진 요소("
            + ", ".join(weak["uncertain_without_prior"])
            + ")가 있어, 이 목록에 실제로는 대응되는 요소가 섞여 있을 수 있습니다."
        )
    if weak["prior_only"]:
        st.dataframe(
            [
                {
                    "P": p["id"],
                    "기존 논문 요소": p["text"],
                    "근거 위치": f"P[{p['section']}]" if p.get("section") else "-",
                    "판단 이유": p["reason"],
                }
                for p in weak["prior_only"]
            ],
            hide_index=True,
        )
    else:
        st.success("기존 논문의 모든 요소가 내 논문 요소와 대응됩니다.")

    st.markdown(f"**동일 조건에서 수치가 낮은 실험** · {weak['counts']['inferior_results']}개")
    if weak["inferior_results"]:
        st.dataframe(
            [
                {
                    "데이터셋": r.get("dataset") or "-",
                    "지표": r.get("metric") or "-",
                    "내 수치": f"{r['my_result_id']}: {r.get('my_value') or '-'}",
                    "기존 수치": f"{r['prior_result_id']}: {r.get('prior_value') or '-'}",
                    "차이(내−기존)": _fmt_diff(r.get("difference"), r.get("difference_unit")),
                    "근거": f"{r['my_text']}  ↔  {r['prior_text']}",
                }
                for r in weak["inferior_results"]
            ],
            hide_index=True,
        )
    else:
        st.info("동일 조건에서 기존 논문보다 낮은 실험 결과가 없습니다. (비교 가능한 실험이 없는 경우 포함)")


def render_numeric(verified, ids):
    st.subheader("정량 비교")
    checks = verified.get("numeric_checks") or []
    if not checks:
        st.info("직접 비교 가능한 실험이 없습니다.")
        return

    rm_text = {r["id"]: r["text"] for r in ids["RM"]}
    rp_text = {r["id"]: r["text"] for r in ids["RP"]}
    rows = []
    for c in checks:
        diff = c.get("absolute_difference")
        unit = c.get("absolute_difference_unit") or ""
        rows.append({
            "내 결과": f"{c['my_result_id']}. {rm_text.get(c['my_result_id'], '')}",
            "기존 결과": f"{c['prior_result_id']}. {rp_text.get(c['prior_result_id'], '')}",
            "결과": c["outcome"],
            "차이(내−기존)": _fmt_diff(diff, unit),
            "조건(에이전트)": c.get("agent_condition") or "-",
            "사유": c.get("reason") or "",
            "경고": " / ".join(c.get("warnings") or []),
        })
    st.dataframe(rows, hide_index=True)


def render_report(compare):
    st.subheader("차별성 리포트")
    st.markdown("**요약**")
    # 여러 문장으로 나뉘어 나온 경우도 모두 보여준다 (validator 는 이어 붙여 검증한다).
    st.text(" ".join(_list(compare, "summary")) or "-")

    st.markdown("**주의 지점**")
    for item in _list(compare, "caution_points") or ["-"]:
        st.text(f"• {item}")

    st.markdown("**서술 제안**")
    for i, item in enumerate(_list(compare, "differentiation_suggestions") or ["-"], start=1):
        st.text(f"{i}. {item}")

    st.subheader("Related Work 초안")
    st.code(" ".join(_list(compare, "related_work_draft")) or "-", language=None, wrap_lines=True)
    st.caption("오른쪽 위 아이콘으로 복사할 수 있습니다.")


def render_uncertain(verified):
    st.subheader("확인 필요 목록")
    items = verified.get("uncertain_items") or []
    if not items:
        st.success("확인이 필요한 요소가 없습니다.")
        return
    if verified["final_level"] == "판정 보류":
        st.caption("이 항목을 확인하면 등급이 확정됩니다.")
    for item in items:
        with st.container(border=True):
            st.text(f"{item['id']}. {item['text']}")
            for reason in item["reasons"]:
                st.caption(f"사유: {reason}")


def render_suitability(suitability):
    st.subheader("비교 적합성")
    relation_labels = {
        "same": "같음", "related": "관련 있음", "different": "다름",
        "unknown": "확인 불가", "comparable": "대응 가능", "partial": "일부 공통",
        "specific_shared": "구체적 방법 연결", "generic_only": "범용 기반만 공통",
    }
    rows = []
    for key, axis in suitability["axes"].items():
        rows.append({"판단 기준": AXIS_LABELS[key],
                     "관계": relation_labels.get(axis["relation"], axis["relation"]),
                     "이유": axis["reason"]})
    st.dataframe(rows, hide_index=True)
    for warning in suitability.get("warnings", []):
        st.warning(warning)
    with st.expander("적합성 판단 근거 (추출본)"):
        st.caption("추출본의 인용 일치를 검사했습니다. PDF 원문에 대한 의미 검증은 별도로 필요합니다.")
        for key, axis in suitability["axes"].items():
            st.markdown(f"**{AXIS_LABELS[key]}**")
            for label, field in (("내 논문", "my_evidence"), ("기존 논문", "prior_evidence")):
                for evidence in axis[field]:
                    st.text(f"{label} · {evidence['field']}[{evidence['index']}]")
                    st.text(evidence["source_text"])


def render_result(bundle, key_prefix):
    suitability = bundle.get("suitability")
    if suitability is None:
        st.warning("적합성 판정 도입 전의 저장 결과입니다. 현재 기준의 레포트를 받으려면 다시 분석해 주세요.")
        suitability = deferred_assessment("저장된 결과에 비교 적합성 판단과 근거가 없습니다.")
    verified = bundle.get("verified")
    # 표시 정책은 저장된 플래그가 아닌 현재 코드에서 다시 결정한다.
    report = build_report(suitability, verified)
    st.subheader(report["title"])
    st.info(report["summary"])
    render_suitability(suitability)

    ids = assign_ids(bundle["my_paper"], bundle["prior_paper"])
    if verified is not None:
        if verified.get("status") != "PASSED":
            st.warning("코드 검증에 재확인할 항목이 있습니다. 검증 상세와 근거를 확인하세요.")
        if report["show_overall_grade"]:
            render_badges(verified)
            st.caption("커버리지는 추출 요소의 겹침 지표이며 신뢰도나 독창성 확률이 아닙니다.")
        if report["show_mappings"]:
            st.divider()
            if suitability["route"] != "research":
                st.caption("요소 대응은 공통 범위·방법의 관계를 검토하기 위한 자료입니다. 전체 연구의 차별성으로 해석하지 마세요.")
            render_mapping_table(verified, ids)
        if report["show_novelty_candidates"]:
            render_novel_overlap(verified, ids, bundle.get("insight"))
            st.caption("대응 없음은 선택한 비교 논문의 추출 범위에 한정됩니다. 원문을 다시 확인하세요.")
        if report["show_weaknesses"]:
            render_weakness(verified, ids)
        if report["show_numeric"]:
            st.subheader(f"실험 비교 가능 여부 · {report['numeric']['status']}")
            render_numeric(verified, ids)
        else:
            st.info("이 경로에서는 연구 간 성능 우위를 제시하지 않습니다.")
        if report["show_mappings"]:
            render_uncertain(verified)
            render_insight(bundle.get("insight"))
        with st.expander(f"검증 상세 (status: {verified['status']}, 이슈 {len(verified['issues'])}건)"):
            st.dataframe(
                [{"코드": i["code"], "심각도": i["severity"], "항목": i.get("item_id") or "",
                  "설명": i["message"]} for i in verified["issues"]], hide_index=True,
            )
        if suitability["route"] == "research" and verified.get("status") != "FAILED":
            with st.expander("AI 서술 초안 (검증 결과 반영 전)"):
                st.warning("아래는 AI 원출력입니다. 수치·조건·등급이 최종 검증과 다를 수 있어 원문 확인 후 사용해야 합니다.")
                render_report(bundle.get("compare_result") or {})

    st.subheader("다음 행동")
    for action in report["next_actions"]:
        st.text(f"• {action}")
    with st.expander("비교 범위와 제한"):
        for limitation in report["limitations"]:
            st.text(f"• {limitation}")
    st.download_button(
        "최종 레포트 JSON 다운로드",
        json.dumps({"suitability": suitability, "report": report, "verified": verified},
                   ensure_ascii=False, indent=2),
        file_name="report.json", mime="application/json", key=f"{key_prefix}_dl_report",
    )
    if verified is not None and suitability["comparison_allowed"]:
        st.download_button(
            "검증 결과 JSON 다운로드", json.dumps(verified, ensure_ascii=False, indent=2),
            file_name="verified_result.json", mime="application/json", key=f"{key_prefix}_dl_verified",
        )
        with st.expander("원본 AI 출력 다운로드"):
            st.caption("검증·범위 제한 전의 진단 자료입니다. 최종 레포트와 구분해 사용하세요.")
            st.download_button(
                "원본 compare_result.json", json.dumps(bundle.get("compare_result"), ensure_ascii=False, indent=2),
                file_name="compare_result.json", mime="application/json", key=f"{key_prefix}_dl_compare",
            )


##################################################
# Tabs
##################################################

def render_privacy_notice():
    st.info(
        "업로드한 논문은 분석을 위해 Upstage API로 전송됩니다. "
        f"서버에 저장된 PDF와 분석 결과는 {_hours_text()} 뒤 자동 삭제되며, "
        "결과 화면 아래 버튼으로 바로 삭제할 수도 있습니다. "
        "공개 전 논문이라면 소속 기관의 보안 규정을 먼저 확인해 주세요.",
        icon="🔒",
    )


def render_delete_button(bundle, divider=True):
    """
    이번 실행의 서버 파일(runs/<run_id>/)을 바로 지운다.
    분석 전(업로드만 한 상태)·실패 후·완료 후 모두 쓸 수 있고, 분석 중에는 지우지 않는다.
    """
    run_dir = bundle.get("run_dir")
    if not run_dir or is_running(run_dir):
        return
    if divider:
        st.divider()
    if st.session_state.get("deleted_run") == run_dir:
        st.success("서버에 저장된 이번 분석 파일(논문 PDF, 결과 JSON)을 삭제했습니다. 이 화면을 닫으면 결과도 사라지니 필요하면 먼저 다운로드하세요.")
        return
    st.caption(f"서버에 저장된 이번 분석 파일(올린 PDF와 결과)은 {_hours_text()} 뒤 자동 삭제됩니다.")
    if st.button("🗑️ 이번 분석 파일 지금 삭제", key="delete_run"):
        if delete_run(run_dir):
            st.session_state["deleted_run"] = run_dir
            _reset_run()  # 주소와 업로드 칸도 비워서, 지운 파일이 다시 저장되지 않게 한다
            st.rerun()
        else:
            st.error("삭제하지 못했습니다. 이미 삭제되었거나 실행 폴더가 아닙니다.")


def _current_run_dir():
    """URL의 ?run=<run_id>로 실행 폴더를 찾는다. 새로고침해도 같은 폴더로 돌아온다."""
    return run_dir_from_id(st.query_params.get("run"))


def _ensure_run_dir(run_dir):
    if run_dir is None:
        run_dir = new_run_dir()
        st.query_params["run"] = run_dir.name
    return run_dir


def _run_state(run_dir):
    if run_dir is None:
        return {"status": "idle", "files": {}}
    state = read_state(run_dir)
    if state.get("status") == "running" and not is_running(run_dir):
        # running인데 lock이 없으면 서버 재시작 등으로 실행이 끊긴 것이다.
        state = update_state(run_dir, status="failed", error={
            "step": state.get("step") or "실행",
            "message": "서버가 다시 시작되어 분석이 중단되었습니다. 다시 시작해 주세요."})
    return state


def _reset_run():
    st.query_params.clear()
    st.session_state["upload_gen"] = st.session_state.get("upload_gen", 0) + 1
    for kind in UPLOAD_SAMPLES:
        st.session_state[f"replace_{kind}"] = False


def _start(run_dir, focus):
    # on_click 콜백은 화면을 다시 그리기 전에 실행된다. 여기서 lock과 running을 기록하므로
    # 다음 화면에서 버튼은 이미 잠겨 있다 (멘토링 11/05: 진행 중 중복 클릭 방지).
    from service import start_in_background

    st.session_state.pop("deleted_run", None)
    if not start_in_background(run_dir, focus):
        st.session_state["start_msg"] = "이미 진행 중인 분석이 있습니다. 끝날 때까지 기다려 주세요."


def _set_replace(kind, value):
    st.session_state[f"replace_{kind}"] = value


def render_uploads(run_dir, running):
    """
    저장된 PDF가 있으면 업로드 칸 대신 파일 카드를 보여준다.
    브라우저는 보안상 새로고침 후 업로드 칸에 파일을 다시 채울 수 없어서,
    빈 업로드 칸만 보이면 사용자는 파일이 사라졌다고 느낀다 (11/06 확인).
    """
    files = _run_state(run_dir).get("files", {})
    gen = st.session_state.get("upload_gen", 0)
    left, right = st.columns(2)
    for col, kind, label in ((left, "my", "투고할 내 논문 PDF"), (right, "prior", "비교할 기존 논문 PDF")):
        with col:
            info = files.get(kind)
            replacing = st.session_state.get(f"replace_{kind}", False)

            if info and not replacing:
                st.markdown(label)
                with st.container(border=True):
                    pages = info.get("pages")
                    st.markdown(f"📄 **{info['name']}**")
                    st.caption(f"{pages or '?'}쪽 · {info['size'] // 1024:,} KB · 서버에 저장됨 (새로고침해도 유지)")
                    saved = Path(run_dir) / UPLOAD_SAMPLES[kind]
                    c1, c2 = st.columns(2)
                    if saved.exists():
                        c1.download_button("PDF 다시 받기", saved.read_bytes(), file_name=info["name"],
                                           mime="application/pdf", key=f"saved_{kind}", use_container_width=True)
                    c2.button("다른 파일로 바꾸기", key=f"replace_btn_{kind}", disabled=running,
                              on_click=_set_replace, args=(kind, True), use_container_width=True)
                if pages and pages > PAGE_MAX:
                    st.warning(f"{PAGE_MAX}쪽이 넘으면 시간 초과로 실패할 수 있습니다. 부록을 뺀 본문만 올리는 것을 권합니다.")
                elif pages and pages > PAGE_WARN:
                    st.caption(f"{pages}쪽이라 분석이 평소보다 오래 걸릴 수 있습니다.")
            else:
                up = st.file_uploader(label, type=["pdf"], key=f"{kind}_pdf_{gen}", disabled=running)
                if up is not None:
                    data = up.getvalue()
                    # 같은 파일이면 다시 저장하지 않는다 (저장하면 이전 결과가 지워진다).
                    if (info or {}).get("sha256") != hashlib.sha256(data).hexdigest():
                        run_dir = _ensure_run_dir(run_dir)
                        files[kind] = save_upload(run_dir, kind, up.name, data)
                    st.session_state[f"replace_{kind}"] = False
                    st.rerun()  # 바로 파일 카드로 바꿔 보여준다
                if replacing:
                    st.button("바꾸지 않기", key=f"cancel_replace_{kind}", on_click=_set_replace, args=(kind, False))

            name = UPLOAD_SAMPLES[kind]
            path = SAMPLES_DIR / name
            if path.exists() and not files.get(kind):
                st.download_button(f"샘플 {name} 받기", path.read_bytes(), file_name=name, key=f"sample_{name}")
    return run_dir, files


def render_focus(state, disabled):
    saved = normalize_focus(state.get("focus"))
    with st.expander("관심 초점 고르기 (선택)", expanded=bool(saved["aspects"] or saved["goals"])):
        st.caption("고르면 주의 지점, 서술 제안, 관계 분석이 이 항목을 먼저 다룹니다. 요소 대응표와 등급 계산은 바뀌지 않습니다.")
        focus = {"aspects": [], "goals": []}
        c1, c2 = st.columns(2)
        c1.markdown("**보고 싶은 측면**")
        for key, (label, _) in ASPECTS.items():
            if c1.checkbox(label, value=key in saved["aspects"], key=f"aspect_{key}", disabled=disabled):
                focus["aspects"].append(key)
        c2.markdown("**얻고 싶은 것**")
        for key, (label, _) in GOALS.items():
            if c2.checkbox(label, value=key in saved["goals"], key=f"goal_{key}", disabled=disabled):
                focus["goals"].append(key)
    return focus


@st.fragment(run_every=2)
def render_progress(run_dir):
    """2초마다 state.json을 다시 읽는다. 끝나면 화면 전체를 다시 그려 결과를 보여준다."""
    state = _run_state(run_dir)
    if state.get("status") != "running":
        st.rerun()
    current = state.get("step") or "실행 준비"
    index = STEP_ORDER.index(current) if current in STEP_ORDER else -1
    with st.container(border=True):
        st.markdown(f"**분석 중 · {current}**")
        for i, name in enumerate(STEP_ORDER):
            if name.startswith("8단계") and not insight_agent.is_enabled():
                continue
            mark = "✅" if i < index else "⏳" if i == index else "▫️"
            st.text(f"{mark} {name}")
        if started := state.get("started_at"):
            st.caption(f"경과 {int(time.time() - started)}초 · 새로고침하거나 창을 닫아도 분석은 계속됩니다. "
                       "이 주소로 다시 오면 결과를 볼 수 있습니다.")


def tab_new_analysis():
    render_privacy_notice()

    run_dir = _current_run_dir()
    running = _run_state(run_dir).get("status") == "running"

    run_dir, files = render_uploads(run_dir, running)
    state = _run_state(run_dir)

    problems = []
    if "my" not in files:
        problems.append("내 논문 PDF를 올려 주세요.")
    if "prior" not in files:
        problems.append("기존 논문 PDF를 올려 주세요.")
    if "my" in files and "prior" in files and files["my"]["sha256"] == files["prior"]["sha256"]:
        problems.append("두 칸에 같은 파일이 올라갔습니다. 서로 다른 논문을 올려 주세요.")
    if not running:
        for p in problems:
            st.caption(f"⚠️ {p}")

    focus = render_focus(state, running)

    c1, c2 = st.columns([3, 1])
    c1.button("분석하는 중…" if running else "비교 시작", type="primary", use_container_width=True,
              disabled=running or bool(problems), on_click=_start, args=(run_dir, focus))
    c2.button("새 비교", use_container_width=True, disabled=running, on_click=_reset_run)
    if msg := st.session_state.pop("start_msg", None):
        st.warning(msg)

    if running:
        render_progress(run_dir)
        return

    if state.get("status") == "failed":
        error = state.get("error") or {}
        st.error(f"{error.get('step', '실행')}에서 실패했습니다.\n{error.get('message', '')}")
        st.caption("이전 결과로 대신 채우지 않았습니다. 원인을 확인한 뒤 다시 시작해 주세요.")
        render_delete_button({"run_dir": str(run_dir)})
    elif state.get("status") == "done":
        bundle = load_bundle(run_dir)
        if bundle is None:
            st.warning("결과 파일을 찾지 못했습니다. 보관 기간이 지나 삭제되었을 수 있습니다. 다시 분석해 주세요.")
            return
        if state.get("elapsed"):
            st.caption(f"분석 시간 {state['elapsed']:g}초")
        st.divider()
        render_result(bundle, "new")
        render_delete_button(bundle)
    elif st.session_state.get("deleted_run"):
        st.success("서버에 저장된 분석 파일(논문 PDF, 결과 JSON)을 삭제했습니다.")
    elif run_dir is not None and files:
        # 분석 전이라도 올린 PDF는 서버에 저장돼 있으므로 바로 지울 수 있게 한다.
        render_delete_button({"run_dir": str(run_dir)})


def tab_sample():
    bundle = {}
    for key, name in SAMPLE_FILES.items():
        path = SAMPLES_DIR / name
        if not path.exists():
            st.info(f"샘플 파일이 없습니다: samples/{name}")
            return
        bundle[key] = json.loads(path.read_text(encoding="utf-8"))

    suitability_path = SAMPLES_DIR / "suitability.json"
    if suitability_path.exists():
        bundle["suitability"] = json.loads(suitability_path.read_text(encoding="utf-8"))
    st.caption("미리 실행해 둔 결과입니다. 에이전트를 호출하지 않습니다.")
    render_result(bundle, "sample")


##################################################
# Main
##################################################

def main():
    st.set_page_config(page_title="PriorScope", page_icon="📄", layout="wide")
    st.html(PAGE_STYLES)

    # 보관 기간이 지난 실행 폴더 정리. 화면이 열릴 때마다 부르지 않도록 세션당 한 번만 한다.
    if not st.session_state.get("runs_cleaned"):
        try:
            cleanup_old_runs()
        except Exception:  # noqa: BLE001
            pass
        st.session_state["runs_cleaned"] = True
    st.title("PriorScope · 논문 차별성 사전 점검")
    st.caption("두 논문의 비교 적합성을 먼저 판단한 뒤, 공통 범위와 근거에 맞는 레포트를 제공합니다.")

    new_tab, sample_tab = st.tabs(["새로 분석", "샘플 결과 보기"])
    with new_tab:
        tab_new_analysis()
    with sample_tab:
        tab_sample()

    st.divider()
    st.caption(
        "사전 점검용이며 심사·표절 판정을 대체하지 않습니다. "
        f"업로드한 논문과 결과는 서버에 {_hours_text()} 보관 후 자동 삭제됩니다."
    )


if __name__ == "__main__":
    main()
