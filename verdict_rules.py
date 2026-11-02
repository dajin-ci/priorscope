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


##################################################
# Studio 에 붙여 넣는 요약 문구
##################################################

# Studio 필드 설명·지시문은 1000바이트 제한이 있다 (한글은 글자당 3바이트).
# 자세한 기준은 Compare_Input.pdf 안내문(compare_builder.GUIDE_LINES)에 모두 들어가므로,
# Studio 쪽은 그 안내를 따르라고 가리키고 핵심만 요약한다.
STUDIO_LIMIT_BYTES = 1000

STUDIO_ELEMENT_MAPPING = "\n".join([
    "M마다 한 줄: M2 ↔ P4,P5 | 유사 | M[3.1] / P[2.3] | 설명",
    "대응 없음: M3 ↔ - | 없음 | 검토 범위 P1~Pn | 설명",
    "판정은 문서 안내의 판정 기준을 따른다. 요약:",
    "일치=기존 P를 그대로 씀(사전학습 모델·임베딩 공간 포함)",
    "유사=같은 역할로 방식만 변형·교체",
    "없음=기존에 없음. P 제거, 학습 규모·설정값만 변경, 범용 기법만 공통도 없음. P칸은 -, 설명에 관련 P",
    "확인필요=판단이 안 서면 없음 대신 쓴다",
    "다른 용어·언어로 쓴 같은 기술도 대응으로 본다",
])

STUDIO_INSTRUCT = "\n".join([
    "입력은 내 논문(M, R-M)과 기존 논문(P, R-P) 비교 자료다. 문서의 번호만 쓴다.",
    "1) M마다 대응을 쓴다: M2 ↔ P4,P5 | 유사 | M[3.1] / P[2.3] | 이유. 없으면 M3 ↔ - | 없음 | 검토 범위 P1~Pn | 이유. "
    "판정은 문서 안내의 기준을 따른다. 핵심: 심사자가 '기존 논문에 이미 있다'고 반박할 수 있으면 일치·유사, 아니면 없음. "
    "확신 없으면 확인필요.",
    "2) 데이터셋·지표가 같은 실험 쌍: R-M1 ~ R-P2 | 동일 조건 또는 조건 다름 | 이유",
    "3) 1)의 판정으로 등급을 정한다. High Overlap: 핵심 요소 대부분이 이미 있음. Medium Overlap: 일부 겹치나 고유 구성 있음. "
    "Low Overlap: 분야만 비슷함. 등급과 이유를 M 번호를 들어 2~3문장으로 쓴다.",
])


if __name__ == "__main__":
    for name, text in (("Extract · element_mapping 원소 설명", STUDIO_ELEMENT_MAPPING),
                       ("지시-1 · 지시문", STUDIO_INSTRUCT)):
        print(f"===== {name} ({len(text.encode('utf-8'))}/{STUDIO_LIMIT_BYTES} bytes)")
        print(text)
        print()
