"""
insight_agent.py

8단계(선택, 멘토링 11/05). 7단계까지 검증·합치기가 끝난 대응표를 바탕으로 LLM을 한 번 더 호출해
  (1) 두 논문 주장 사이의 관계: 확장 / 보완 / 상충 / 연결
      예) 기존 논문은 A→B, 내 논문은 B→C를 보였다면 '연결'로 A→C 함의를 짚는다.
  (2) 겹치는 요소 활용법: 겹치는 안에서 내 쪽이 다른 점, 본문 서술 방식, 리뷰어 예상 질문
을 정리한다. 입력은 PDF가 아니라 이미 추출된 텍스트라 비용이 적다.

적합성 판단(suitability.py)처럼 Upstage Chat Completions를 직접 호출한다 (Studio 에이전트 아님).
INSIGHT_MODEL 이 비어 있으면 이 단계를 건너뛴다.

원칙은 앞 단계와 같다. LLM은 의미 판단만 하고 번호 검증·필터링은 코드가 한다.
- 없는 M/P 번호를 쓴 항목은 버리고 dropped에 남긴다.
- '연결'은 어느 논문도 직접 검증하지 않은 추론일 수 있어 항상 inferred=True로 표시한다.
- 확인필요 요소가 섞인 관계는 uncertain_ids로 표시한다.
- 등급·커버리지·경로는 다시 계산하지 않는다.
"""

import json
import re
import time

from ids import as_list, assign_ids, first

RELATION_TYPES = {"확장", "보완", "상충", "연결"}
MAX_RELATIONS = 5
ALLOWED_ROUTES = {"research", "partial", "method"}
_ID = re.compile(r"[MP]\d+")


##################################################
# 설정
##################################################

def is_enabled():
    from config import INSIGHT_MODEL
    return bool(INSIGHT_MODEL)


def backend_label():
    from config import INSIGHT_MODEL
    return f"Upstage · {INSIGHT_MODEL}" if is_enabled() else None


##################################################
# 프롬프트
##################################################

SYSTEM_PROMPT = """너는 논문의 차별성 분석을 돕는 연구 조교다. 사용자가 준 두 논문 정보만 근거로 쓰고, 정보에 없는 내용은 지어내지 않는다.
JSON 객체 하나만 출력한다. 마크다운 코드블록이나 설명 문장을 붙이지 않는다.

출력 형식:
{"relations": [...], "overlap_insights": [...], "focus_notes": [...]}

relations: 두 논문 주장 사이의 관계. 최대 5개. 뚜렷한 관계가 없으면 빈 배열.
  type: "확장" | "보완" | "상충" | "연결"
    확장: 기존 논문의 방법이나 결과를 전제로 내 논문이 한 단계 더 나아간다.
    보완: 기존 논문이 스스로 밝힌 한계를 내 논문이 다룬다.
    상충: 같은 대상과 조건에 대해 두 논문의 주장이나 결론이 다르다.
    연결: 기존 논문은 A→B를, 내 논문은 B→C를 보였을 때 둘을 이으면 A→C 같은 함의가 나온다. 어느 논문도 A→C를 직접 검증하지 않았다면 insight에 그 점을 적는다.
  my_ids: 관련 M 번호 배열, prior_ids: 관련 P 번호 배열 (입력에 있는 번호만)
  prior_claim: 기존 논문이 그 지점에서 하는 주장 한 문장
  my_claim: 내 논문이 그 지점에서 하는 주장 한 문장
  insight: 연구자가 논문에 바로 쓸 수 있는 시사점 1~2문장
  evidence: "M[섹션] / P[섹션]" 형식

overlap_insights: 판정이 일치 또는 유사인 M마다 하나.
  my_id: M 번호, prior_ids: 대응한 P 번호 배열
  delta: 겹치는 안에서도 내 논문 쪽이 다른 점. 입력에 근거가 없으면 "확인 필요"라고 쓴다.
  how_to_write: 본문에서 이 요소를 기존 논문 대비 어떻게 서술할지 한 문장 (예: "~를 따르되 ~를 바꾼다")
  reviewer_question: 리뷰어가 물을 법한 질문 한 문장

focus_notes: 사용자 관심 초점에 맞춘 조언 0~3개. 관심 초점이 없으면 빈 배열.

규칙:
- 비교 경로가 research가 아니면 전체 연구의 신규성이나 성능 우위를 말하지 않고, 공통 범위·방법의 관계만 쓴다.
- 판정이 확인필요인 M을 "새롭다", "최초"라고 쓰지 않는다.
- 판정이 없음 또는 확인필요인 M은 overlap_insights에 넣지 않는다.
- 답은 한국어로 쓴다. 기술 용어는 원문 표현을 그대로 써도 된다."""


def _bullets(items):
    items = as_list(items)
    return [f"- {x}" for x in items] if items else ["- (없음)"]


def build_user_prompt(my, prior, verified, focus=None, route="research"):
    from focus import focus_lines

    p_items = assign_ids(my, prior)["P"]
    lines = [f"[비교 경로] {route}", "", "[내 논문]", f"제목: {first(my, 'title')}", "기여점:"]
    lines += _bullets(my.get("contributions"))
    lines.append("핵심 요소와 검증된 판정 (번호: 판정 ↔ 대응 P | 요소):")
    for m in verified.get("mappings", []):
        prior_ids = ",".join(m.get("prior_ids") or []) or "-"
        lines.append(f"{m['id']}: {m['final_verdict']} ↔ {prior_ids} | {m['text']}")

    lines += ["", "[기존 논문]", f"제목: {first(prior, 'title')}", f"인용 정보: {first(prior, 'citation_info')}", "핵심 요소:"]
    lines += [f"{p['id']}: {p['text']}" for p in p_items]
    lines.append("기존 논문이 스스로 밝힌 한계:")
    lines += _bullets(prior.get("limitations"))

    lines += ["", "[사용자 관심 초점]"]
    lines += focus_lines(focus) or ["(선택 없음)"]
    return "\n".join(lines)


##################################################
# 응답 정리 (코드 검증)
##################################################

def _parse_json(text):
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("응답에서 JSON 객체를 찾지 못했습니다.")
    return json.loads(text[start:end + 1])


def _ids(value):
    if isinstance(value, str):
        value = re.split(r"[,\s]+", value)
    if not isinstance(value, list):
        return []
    out = []
    for v in value:
        v = str(v).strip()
        if _ID.fullmatch(v) and v not in out:
            out.append(v)
    return out


def _dicts(value):
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _text(value):
    return str(value).strip() if value is not None else ""


def clean_insight(raw, verified, p_ids):
    verdict = {m["id"]: m["final_verdict"] for m in verified.get("mappings", [])}
    overlapping = {mid for mid, v in verdict.items() if v in ("일치", "유사")}
    p_ids = set(p_ids)
    dropped = []

    relations = []
    for i, r in enumerate(_dicts(raw.get("relations"))):
        rtype = _text(r.get("type"))
        mine, prior = _ids(r.get("my_ids")), _ids(r.get("prior_ids"))
        unknown = [x for x in mine if x not in verdict] + [x for x in prior if x not in p_ids]
        if rtype not in RELATION_TYPES:
            dropped.append({"where": f"relations[{i}]", "reason": f"관계 유형이 4종 밖: {rtype!r}"})
            continue
        if not mine or not prior or unknown:
            dropped.append({"where": f"relations[{i}]", "reason": f"번호 없음 또는 없는 번호: {unknown or '빈 값'}"})
            continue
        relations.append({
            "type": rtype,
            "my_ids": mine,
            "prior_ids": prior,
            "prior_claim": _text(r.get("prior_claim")),
            "my_claim": _text(r.get("my_claim")),
            "insight": _text(r.get("insight")),
            "evidence": _text(r.get("evidence")),
            "inferred": rtype == "연결",
            "uncertain_ids": [x for x in mine if verdict.get(x) == "확인필요"],
        })
    if len(relations) > MAX_RELATIONS:
        dropped.append({"where": "relations", "reason": f"{MAX_RELATIONS}개 초과분 제외"})
        relations = relations[:MAX_RELATIONS]

    overlaps, seen = [], set()
    for i, o in enumerate(_dicts(raw.get("overlap_insights"))):
        mid = _text(o.get("my_id"))
        if mid not in overlapping or mid in seen:
            dropped.append({"where": f"overlap_insights[{i}]", "reason": f"겹침 요소가 아니거나 중복: {mid!r}"})
            continue
        seen.add(mid)
        overlaps.append({
            "my_id": mid,
            "prior_ids": [x for x in _ids(o.get("prior_ids")) if x in p_ids],
            "delta": _text(o.get("delta")) or "확인 필요",
            "how_to_write": _text(o.get("how_to_write")),
            "reviewer_question": _text(o.get("reviewer_question")),
        })

    notes = [_text(n) for n in raw.get("focus_notes") or [] if _text(n)][:3] if isinstance(raw.get("focus_notes"), list) else []
    return {"relations": relations, "overlap_insights": overlaps, "focus_notes": notes, "dropped": dropped}


##################################################
# LLM 없이 계산하는 부분
##################################################

def citation_points(my, prior, verified):
    """겹치는 요소마다 Related Work에서 인용할 기존 논문 위치. LLM 호출 없이 만든다."""
    p_by_id = {p["id"]: p for p in assign_ids(my, prior)["P"]}
    citation = first(prior, "citation_info")
    points = []
    for m in verified.get("mappings", []):
        if m["final_verdict"] not in ("일치", "유사"):
            continue
        sections = sorted({p_by_id[p]["section"] for p in m["prior_ids"] if p in p_by_id and p_by_id[p]["section"]})
        points.append({
            "my_id": m["id"],
            "verdict": m["final_verdict"],
            "prior_ids": m["prior_ids"],
            "prior_sections": sections,
            "citation": citation,
        })
    return points


##################################################
# 실행
##################################################

def run_insight(my, prior, verified, focus=None, *, route="research", client=None):
    from config import INSIGHT_MODEL, UPSTAGE_API_KEY, UPSTAGE_HEADERS

    if not INSIGHT_MODEL:
        raise RuntimeError("INSIGHT_MODEL이 설정되지 않았습니다.")
    if route not in ALLOWED_ROUTES:
        raise ValueError(f"관계 분석을 하지 않는 경로입니다: {route}")

    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=UPSTAGE_API_KEY, base_url="https://api.upstage.ai/v1",
                        default_headers=UPSTAGE_HEADERS, timeout=120, max_retries=1)
    t0 = time.time()
    response = client.chat.completions.create(
        model=INSIGHT_MODEL,
        temperature=0.2,
        max_tokens=3000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(my, prior, verified, focus, route)},
        ],
    )
    text = response.choices[0].message.content or ""

    p_ids = [p["id"] for p in assign_ids(my, prior)["P"]]
    result = clean_insight(_parse_json(text), verified, p_ids)
    result.update({
        "route": route,
        "backend": backend_label(),
        "elapsed": round(time.time() - t0, 1),
        "citation_points": citation_points(my, prior, verified),
    })
    return result
