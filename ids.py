"""
ids.py
compare_builder.py와 validator.py가 함께 쓰는 번호 부여 규칙.
같은 JSON이 들어오면 항상 같은 번호가 나온다.

  내 논문   core_techniques    -> M1, M2, ...
  기존 논문 core_techniques    -> P1, P2, ...
  내 논문   experiment_results -> R-M1, R-M2, ...
  기존 논문 experiment_results -> R-P1, R-P2, ...
"""

import re

# "[3.1] 원문 | 설명" 에서 3.1 을 꺼낸다
SECTION_PATTERN = re.compile(r"^\s*\[([^\]]+)\]")


# Studio Parse가 PDF 줄바꿈을 <br/>로 남기는 경우가 있다. 예: "architec-<br/>ture", "ther-<br/>mal"
_HYPHEN_BREAK = re.compile(r"(\w)-\s*<br\s*/?>\s*(\w)", re.IGNORECASE)
_BREAK = re.compile(r"\s*<br\s*/?>\s*", re.IGNORECASE)
_SPACES = re.compile(r"[ \t]{2,}")


def clean_text(text):
    """줄 끝 하이픈으로 끊긴 단어는 붙이고, 나머지 <br/>는 공백으로 바꾼다."""
    text = _HYPHEN_BREAK.sub(r"\1\2", str(text))
    text = _BREAK.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def as_list(value):
    """Studio Extract 결과는 배열이지만, 혹시 문자열이나 None이 와도 리스트로 맞춘다.
    원소마다 <br/> 같은 PDF 줄바꿈 흔적도 정리한다."""
    if value is None:
        return []
    if isinstance(value, list):
        items = [clean_text(v) for v in value]
        return [v for v in items if v]
    text = clean_text(value)
    return [text] if text else []


def first(data, key, default="-"):
    """'단일' 필드는 배열의 첫 값을 쓴다."""
    items = as_list(data.get(key))
    return items[0] if items else default


def section_of(text):
    """요소 앞의 [섹션번호]를 꺼낸다. 없으면 None."""
    match = SECTION_PATTERN.match(text)
    return match.group(1).strip() if match else None


def _number(items, prefix):
    return [
        {"id": f"{prefix}{i}", "text": text, "section": section_of(text)}
        for i, text in enumerate(items, start=1)
    ]


def assign_ids(my_paper, prior_paper):
    """두 논문 JSON에 번호를 붙여 돌려준다."""
    return {
        "M": _number(as_list(my_paper.get("core_techniques")), "M"),
        "P": _number(as_list(prior_paper.get("core_techniques")), "P"),
        "RM": _number(as_list(my_paper.get("experiment_results")), "R-M"),
        "RP": _number(as_list(prior_paper.get("experiment_results")), "R-P"),
    }
