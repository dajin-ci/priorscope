"""
verdict_rules.py

요소 대응 판정(일치·유사·없음·확인필요) 기준. 2026-11-02 팀 확정.

이 기준은 세 곳에서 같은 문구로 쓰인다.
- compare_builder.py: Compare_Input.pdf 안내문 (Compare Agent 가 읽는다)
- eval/labeling.py: 라벨 시트의 라벨 기준 (사람 라벨러가 읽는다)
- Studio Compare Agent 의 element_mapping 설명과 Instruct 지시문 (agent_configs/STUDIO_COMPARE_TEXT.md)
문구를 바꾸면 세 곳을 함께 바꾸고, 라벨도 새 기준으로 다시 확인한다.
"""

PRINCIPLE = ("판정 기준은 '이 M을 기존 논문과 다른 점이라고 주장하면 심사자가 "
             "기존 논문에 이미 있다고 반박할 수 있는가'다.")

RULES = [
    ("일치", "기존 P를 그대로 쓰거나 같은 기법이다. 기존 논문의 사전학습 모델·인코더·임베딩 공간을 그대로 쓰는 경우도 일치다."),
    ("유사", "기존 P와 같은 역할을 유지한 채 방식을 변형·확장·교체했다. 예: 정적 마스킹을 동적 마스킹으로, WordPiece를 BPE로."),
    ("없음", "기존 논문에 없는 요소다. 기존 P를 제거한 것, 학습 규모·기간·배치·데이터 양 같은 설정값만 바꾼 것도 없음이다. "
             "이때 P 칸은 '-'로 두고 설명에 관련 P 번호를 적는다."),
    ("없음", "Transformer 사용, 손실 함수로 학습처럼 범용 기법 수준의 공통점만 있으면 없음이다."),
    ("확인필요", "위 기준으로도 판단이 서지 않으면 없음이 아니라 확인필요로 적는다."),
]

SAME_TECH_NOTE = "같은 기술을 다른 용어나 다른 언어(국문/영문)로 쓴 경우도 대응으로 본다."


def rule_lines() -> list[str]:
    return [PRINCIPLE] + [f"{verdict}: {text}" for verdict, text in RULES] + [SAME_TECH_NOTE]
