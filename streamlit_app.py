"""
streamlit_app.py

PriorScope 결과 화면 (설계서 5장)

탭 1 · 새로 분석      : PDF 2개 → service.run_compare_service() → 결과
탭 2 · 샘플 결과 보기 : samples/ 의 JSON 4개로 같은 화면을 즉시 표시
"""

import hashlib
import json
from pathlib import Path

import streamlit as st

from ids import assign_ids

BASE_DIR = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "samples"
SAMPLE_FILES = {
    "my_paper": "my_paper.json",
    "prior_paper": "prior_paper.json",
    "compare_result": "compare_result.json",
    "verified": "validated_result.json",
}

VERDICT_BADGE = {"일치": "🔴 일치", "유사": "🟠 유사", "없음": "🟢 없음", "확인필요": "🟡 확인필요"}
SHORT_LEVEL = {"High Overlap": "High", "Medium Overlap": "Medium", "Low Overlap": "Low"}


##################################################
# Helpers
##################################################

def _first(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _list(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return [str(value)] if value else []


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
            "근거": m["evidence"],
            "설명": m["explanation"],
            "강등 사유": " / ".join(m["demoted_reasons"]),
        })
    st.dataframe(rows, hide_index=True)


def render_novel_overlap(verified):
    novel = [m for m in verified["mappings"] if m["final_verdict"] == "없음"]
    overlap = [m for m in verified["mappings"] if m["final_verdict"] in ("일치", "유사")]

    left, right = st.columns(2)
    with left:
        st.subheader("내 논문 고유 요소 (차별점)")
        if novel:
            for m in novel:
                st.text(f"{m['id']}. {m['text']}")
        else:
            st.info("검증을 통과한 고유 요소가 없습니다.")
    with right:
        st.subheader("기존 논문과 겹치는 요소")
        if overlap:
            for m in overlap:
                st.text(f"{m['id']} ↔ {','.join(m['prior_ids'])} ({m['final_verdict']}). {m['text']}")
        else:
            st.info("겹치는 요소가 없습니다.")


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
            "차이(내−기존)": f"{diff:+.4g} {unit}".strip() if diff is not None else "-",
            "사유": c.get("reason") or "",
        })
    st.dataframe(rows, hide_index=True)


def render_report(compare):
    st.subheader("차별성 리포트")
    st.markdown("**요약**")
    st.text(_first(compare, "summary") or "-")

    st.markdown("**주의 지점**")
    for item in _list(compare, "caution_points") or ["-"]:
        st.text(f"• {item}")

    st.markdown("**서술 제안**")
    for i, item in enumerate(_list(compare, "differentiation_suggestions") or ["-"], start=1):
        st.text(f"{i}. {item}")

    st.subheader("Related Work 초안")
    st.code(_first(compare, "related_work_draft") or "-", language=None, wrap_lines=True)
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


def render_result(bundle, key_prefix):
    verified = bundle["verified"]
    compare = bundle["compare_result"]
    ids = assign_ids(bundle["my_paper"], bundle["prior_paper"])

    render_badges(verified)
    st.divider()
    render_mapping_table(verified, ids)
    render_novel_overlap(verified)
    st.divider()
    render_numeric(verified, ids)
    st.divider()
    render_report(compare)
    st.divider()
    render_uncertain(verified)

    with st.expander(f"검증 상세 (status: {verified['status']}, 이슈 {len(verified['issues'])}건)"):
        st.dataframe(
            [{"코드": i["code"], "심각도": i["severity"], "항목": i.get("item_id") or "", "설명": i["message"]}
             for i in verified["issues"]],
            hide_index=True,
        )

    d1, d2 = st.columns(2)
    d1.download_button(
        "verified_result.json 다운로드",
        json.dumps(verified, ensure_ascii=False, indent=2),
        file_name="verified_result.json",
        mime="application/json",
        key=f"{key_prefix}_dl_verified",
    )
    d2.download_button(
        "compare_result.json 다운로드",
        json.dumps(compare, ensure_ascii=False, indent=2),
        file_name="compare_result.json",
        mime="application/json",
        key=f"{key_prefix}_dl_compare",
    )


##################################################
# Tabs
##################################################

def tab_new_analysis():
    left, right = st.columns(2)
    my_file = left.file_uploader("투고할 내 논문 PDF", type=["pdf"], key="my_pdf")
    prior_file = right.file_uploader("비교할 기존 논문 PDF", type=["pdf"], key="prior_pdf")

    # 샘플 PDF (samples/ 에 있을 때만 표시)
    for col, name in ((left, "My_Paper.pdf"), (right, "Prior_Paper.pdf")):
        path = SAMPLES_DIR / name
        if path.exists():
            col.download_button(f"샘플 {name} 받기", path.read_bytes(), file_name=name, key=f"sample_{name}")

    problems = []
    if my_file is None:
        problems.append("내 논문 PDF를 올려 주세요.")
    if prior_file is None:
        problems.append("기존 논문 PDF를 올려 주세요.")

    my_bytes = my_file.getvalue() if my_file else None
    prior_bytes = prior_file.getvalue() if prior_file else None
    if my_bytes and prior_bytes and my_bytes == prior_bytes:
        problems.append("두 칸에 같은 파일이 올라갔습니다. 서로 다른 논문을 올려 주세요.")

    for p in problems:
        st.caption(f"⚠️ {p}")

    clicked = st.button("비교 시작", type="primary", disabled=bool(problems))
    current_id = _input_id(my_bytes, prior_bytes) if not problems else None

    if clicked and not problems:
        from service import StepError, run_compare_service

        st.session_state.pop("result", None)
        st.session_state.pop("error", None)

        with st.status("비교 실행 중... (1~3분)", expanded=True) as status:

            def on_step(name):
                status.update(label=name)
                status.write(name)

            try:
                bundle = run_compare_service(my_bytes, prior_bytes, on_step=on_step)
            except StepError as exc:
                status.update(label=f"{exc.step}에서 실패", state="error")
                st.session_state["error"] = (current_id, f"{exc.step}에서 실패했습니다.\n{exc.message}")
            except Exception as exc:  # noqa: BLE001
                status.update(label="실행 실패", state="error")
                st.session_state["error"] = (current_id, f"예상하지 못한 오류: {type(exc).__name__}: {exc}")
            else:
                status.update(label="비교 완료", state="complete", expanded=False)
                st.session_state["result"] = (current_id, bundle)

    error = st.session_state.get("error")
    if error and error[0] == current_id:
        st.error(error[1])

    result = st.session_state.get("result")
    if result and result[0] == current_id:
        st.divider()
        render_result(result[1], "new")


def tab_sample():
    bundle = {}
    for key, name in SAMPLE_FILES.items():
        path = SAMPLES_DIR / name
        if not path.exists():
            st.info(f"샘플 파일이 없습니다: samples/{name}")
            return
        bundle[key] = json.loads(path.read_text(encoding="utf-8"))

    st.caption("미리 실행해 둔 결과입니다. 에이전트를 호출하지 않습니다.")
    render_result(bundle, "sample")


##################################################
# Main
##################################################

def main():
    st.set_page_config(page_title="PriorScope", page_icon="📄", layout="wide")
    st.title("PriorScope · 논문 차별성 사전 점검")
    st.caption("내 논문의 핵심 기술 요소가 기존 논문에 이미 있는지, 근거 위치와 함께 판정합니다.")

    new_tab, sample_tab = st.tabs(["새로 분석", "샘플 결과 보기"])
    with new_tab:
        tab_new_analysis()
    with sample_tab:
        tab_sample()

    st.divider()
    st.caption("사전 점검용이며 심사·표절 판정을 대체하지 않습니다.")


if __name__ == "__main__":
    main()
