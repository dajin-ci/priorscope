"""
focus.py

사용자가 체크박스로 고르는 관심 초점. 자연어 입력 대신 미리 만들어 둔 항목만 쓴다.

- compare_builder.py: Compare_Input.pdf 안내문에 "사용자 관심 초점" 절로 넣는다.
  (Studio 에이전트는 PDF만 입력받으므로 관심 초점도 PDF에 실어 보낸다)
- insight_agent.py: 6단계 관계·인사이트 분석 프롬프트에 넣는다.

관심 초점은 리포트(주의 지점, 서술 제안, 인사이트)의 우선순위만 바꾼다.
요소 대응표의 판정 기준과 등급 계산은 바꾸지 않는다.
"""

# key: (화면 라벨, 에이전트에게 주는 설명)
ASPECTS = {
    "architecture": ("모델 구조·모듈", "네트워크 구조, 모듈 구성, 구성 요소 사이의 연결 방식"),
    "training": ("학습 방법·손실 함수", "학습 절차, 손실 함수, 최적화, 사전학습·미세조정 방식"),
    "data": ("데이터·전처리", "데이터셋 구성, 전처리, 증강, 라벨링 방식"),
    "experiment": ("실험 설계·성능", "실험 조건, 비교 대상(baseline), 지표, 정량 결과"),
    "efficiency": ("효율성", "추론 속도, 메모리, 파라미터 수, 학습 비용"),
    "problem": ("문제 설정·적용 분야", "풀려는 문제의 정의, 가정, 적용 도메인"),
}

GOALS = {
    "related_work": ("Related Work 쓰기", "기존 논문을 어디서 어떻게 인용하고 내 기여를 어떻게 구분해 쓸지"),
    "reviewer": ("리뷰어 질문 대비", "리뷰어가 '기존 연구와 무엇이 다른가'라고 물을 지점과 답할 근거"),
    "next_step": ("후속 연구 아이디어", "기존 논문의 열린 과제 중 내 논문이 이어받거나 더 나아갈 수 있는 지점"),
}


def normalize(focus):
    """화면·state.json에서 온 값을 정해진 key만 남긴 형태로 맞춘다."""
    focus = focus if isinstance(focus, dict) else {}
    aspects = [k for k in focus.get("aspects") or [] if k in ASPECTS]
    goals = [k for k in focus.get("goals") or [] if k in GOALS]
    return {"aspects": aspects, "goals": goals}


def focus_lines(focus):
    """에이전트 입력에 넣을 문장 목록. 고른 것이 없으면 빈 목록."""
    focus = normalize(focus)
    lines = []
    for key in focus["aspects"]:
        label, desc = ASPECTS[key]
        lines.append(f"관심 측면 - {label}: {desc}")
    for key in focus["goals"]:
        label, desc = GOALS[key]
        lines.append(f"얻고 싶은 것 - {label}: {desc}")
    return lines
