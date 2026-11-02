"""최종 사용자 레포트. 비교 경로와 검증 결과로 표시 범위와 서술을 구성한다."""
from collections import Counter
from suitability import ROUTE_LABELS

NEXT_ACTIONS = {
    "research": ["대응표의 근거를 원문에서 확인하고 변경·추가한 기술을 설명하세요."],
    "partial": ["공통으로 다루는 문제와 서로 다른 연구 범위를 먼저 설명하세요.",
                "연구 범위 밖의 요소를 곧바로 약점으로 해석하지 마세요."],
    "method": ["공통 방법의 역할과 적용 대상·전제 조건이 어떻게 달라지는지 설명하세요.",
               "같은 문제를 다루는 논문을 추가로 선택하면 연구 기여를 비교할 수 있습니다."],
    "unsuitable": ["같은 해결 문제를 다루거나 구체적인 핵심 방법이 연결된 기존 논문을 선택하세요."],
    "insufficient": ["논문의 연구 목적·방법이 포함되었는지, PDF 추출이 정상인지 확인하세요.",
                     "누락된 정보나 적합성 분석 오류를 해결한 뒤 다시 분석하세요."],
}


def build_report(suitability, verified=None):
    route = suitability["route"]
    allowed = suitability["comparison_allowed"]
    failed = verified is not None and verified.get("status") == "FAILED"
    checks = (verified or {}).get("numeric_checks", [])
    comparable = [c for c in checks if c.get("outcome") in ("우세", "열세", "동일")]
    numeric_allowed = allowed and not failed and route != "method"
    counts = Counter(c["outcome"] for c in comparable) if numeric_allowed else Counter()
    numeric_status = ("비교 범위 밖" if not allowed or route == "method" else
                      "검증 실패" if failed else "비교 가능" if comparable else "비교 불가·정보 부족")
    summary = {
        "research": "해결 문제와 연구 범위가 대응되어 연구 내용을 비교합니다.",
        "partial": "관련된 문제 중 공통 범위만 검토합니다. 전체 연구의 차별성 등급은 제공하지 않습니다.",
        "method": "해결 문제는 다르지만 구체적인 핵심 방법이 연결되어 방법론을 비교합니다.",
        "unsuitable": "해결 문제와 핵심 방법의 연결이 부족해 차별성·성능 비교를 진행하지 않았습니다.",
        "insufficient": "비교 경로를 정할 정보 또는 근거가 부족해 비교 판단을 보류했습니다.",
    }[route]
    if failed:
        summary += " 비교 결과의 코드 검증이 실패하여 결론을 보류했습니다."
    return {
        "version": "1", "route": route, "title": ROUTE_LABELS[route], "summary": summary,
        "show_mappings": allowed and not failed,
        "show_overall_grade": route == "research" and not failed,
        "show_novelty_candidates": route == "research" and not failed,
        "show_weaknesses": route == "research" and not failed,
        "show_numeric": numeric_allowed,
        "numeric": {"status": numeric_status, "comparable_count": len(comparable) if numeric_allowed else 0,
                    "counts": dict(counts),
                    "incomparable_count": len(checks) - len(comparable) if numeric_allowed else 0},
        "next_actions": NEXT_ACTIONS[route],
        "limitations": ["적합성 근거는 PDF 원문이 아닌 추출본을 대조한 결과입니다.",
                        "범용 기법의 공통점만으로 비교 적합성이나 독창성을 확정하지 않습니다.",
                        "수치 비교는 확인된 평가 조건에 한하며 통계적 우위나 공정한 학습 조건을 보장하지 않습니다."],
    }


def apply_scope_policy(verified, suitability):
    """제한된 비교에서 전체 연구 등급과 방법론 밖의 수치가 최종 결과에 남지 않게 한다."""
    verified["suitability"] = suitability
    verified["overall_assessment_applicable"] = suitability["route"] == "research"
    if suitability["route"] != "research":
        verified["final_level"] = "적용 안 함"
        verified["classify_level"] = None
        verified["classify_agrees"] = None
        verified["llm_score"] = None
        verified["coverage"]["min"] = verified["coverage"]["max"] = None
        verified["weaknesses"] = None
    if suitability["route"] == "method":
        verified["numeric_checks"] = []
    return verified
