"""
compare_builder.py

My Paper Agent와 Prior Paper Agent의 결과(JSON)를 이용하여
Compare_Input.pdf를 생성한다.

요소마다 ids.assign_ids()의 번호(M1, P1, R-M1, R-P1)를 붙여서
Compare Agent가 번호로 대응을 적고 validator.py가 그 번호를 검증할 수 있게 한다.

사용법:
    python compare_builder.py my_paper.json prior_paper.json Compare_Input.pdf
"""

import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from ids import as_list, assign_ids, first

##################################################
# Font
##################################################

FONT_NAME = "Nanum"

DEFAULT_FONT_PATH = Path(__file__).resolve().parent / "fonts" / "NanumGothic-Regular.ttf"


def register_font(font_path=None):
    """
    나눔고딕 등록 (국문 논문 출력용)
    """

    font_path = Path(font_path or DEFAULT_FONT_PATH)

    if not font_path.exists():
        raise FileNotFoundError(f"폰트 파일이 없습니다: {font_path}")

    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))


##################################################
# JSON Load
##################################################

def load_json(path):
    """
    JSON 파일 읽기
    """

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _as_dict(data):
    """
    dict가 오면 그대로, 경로가 오면 읽어서 돌려준다.
    """

    if isinstance(data, (str, Path)):
        return load_json(data)

    return data


##################################################
# Style
##################################################

styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "CompareTitle",
    parent=styles["Heading1"],
    fontName=FONT_NAME,
    fontSize=20,
    leading=28,
    alignment=TA_CENTER,
    spaceAfter=16,
)

HEADING_STYLE = ParagraphStyle(
    "CompareHeading",
    parent=styles["Heading2"],
    fontName=FONT_NAME,
    fontSize=13,
    leading=19,
    spaceBefore=12,
    spaceAfter=6,
)

BODY_STYLE = ParagraphStyle(
    "CompareBody",
    parent=styles["BodyText"],
    fontName=FONT_NAME,
    fontSize=10,
    leading=16,
    spaceAfter=4,
)


##################################################
# PDF Document
##################################################

def create_document(output_pdf):
    """
    PDF Document 생성
    """

    return SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )


##################################################
# Paragraph
##################################################

def paragraph(text, style=BODY_STYLE):
    """
    논문 원문의 <, >, & 를 ReportLab이 태그로 읽지 않도록 escape 한다.
    """

    return Paragraph(escape(str(text)), style)


def add_title(story, title):
    story.append(paragraph(title, TITLE_STYLE))


def add_heading(story, heading):
    story.append(paragraph(heading, HEADING_STYLE))


def add_text(story, text):
    story.append(paragraph(text or "-"))


def add_list(story, items):
    """
    목록 추가. Studio Extract 값은 리스트이므로 원소마다 한 줄씩 쓴다.
    """

    items = as_list(items)

    if not items:
        add_text(story, "-")
        return

    for item in items:
        story.append(paragraph(f"• {item}"))


def add_numbered(story, numbered):
    """
    번호가 붙은 요소 추가

    [{"id": "M1", "text": "..."}, ...] → "M1. ...", ...
    """

    if not numbered:
        add_text(story, "-")
        return

    for item in numbered:
        story.append(paragraph(f"{item['id']}. {item['text']}"))


##################################################
# Guide
##################################################

GUIDE_LINES = [
    "이 문서는 투고할 논문(내 논문)과 기존 논문 1편을 비교하기 위한 입력이다.",
    "내 논문의 핵심 기술 요소는 M1…Mn, 기존 논문의 핵심 기술 요소는 P1…Pn이다.",
    "내 논문의 실험 결과는 R-M1…, 기존 논문의 실험 결과는 R-P1…이다.",
    "각 요소는 '[섹션번호] 원문 표현 | 한국어 설명' 형식이고, "
    "각 실험 결과는 '데이터셋 | 실험 설정 | 지표 | 수치 | 방향 | 위치' 형식이다.",
    "반드시 이 문서에 적힌 번호만 사용하고, 새 번호를 만들지 않는다.",
    "element_mapping은 M 요소마다 한 줄씩 'M2 ↔ P4,P5 | 유사 | M[3.1] / P[2.3] | 설명' 형식으로 쓴다. "
    "대응하는 P가 없으면 'M3 ↔ - | 없음 | 검토 범위 | 설명'으로 쓴다.",
    "판정은 일치, 유사, 없음, 확인필요 중 하나다. "
    "같은 기술을 다른 용어나 다른 언어(국문/영문)로 쓴 경우도 대응으로 본다. "
    "대응을 확신하지 못하면 '없음'이 아니라 '확인필요'로 적는다.",
    "result_pairs는 데이터셋과 지표가 같은 쌍만 'R-M1 ~ R-P2 | 동일 조건 | 설명' 형식으로 쓴다. "
    "실험 설정이 다르면 '조건 다름'으로 쓴다.",
]


def add_guide(story):
    add_title(story, "PriorScope 비교 입력")
    add_heading(story, "안내")

    for line in GUIDE_LINES:
        story.append(paragraph(f"• {line}"))


##################################################
# My Paper
##################################################

def add_my_paper(story, my_paper, ids):
    add_title(story, "내 논문 (My Paper)")

    add_heading(story, "Title")
    add_text(story, first(my_paper, "title"))

    add_heading(story, "Language")
    add_text(story, first(my_paper, "language"))

    add_heading(story, "Problem")
    add_list(story, my_paper.get("problem"))

    add_heading(story, "Core Techniques (M)")
    add_numbered(story, ids["M"])

    add_heading(story, "Contributions")
    add_list(story, my_paper.get("contributions"))

    add_heading(story, "Experiment Results (R-M)")
    add_numbered(story, ids["RM"])


##################################################
# Prior Paper
##################################################

def add_prior_paper(story, prior_paper, ids):
    add_title(story, "기존 논문 (Prior Paper)")

    add_heading(story, "Title")
    add_text(story, first(prior_paper, "title"))

    add_heading(story, "Citation")
    add_text(story, first(prior_paper, "citation_info"))

    add_heading(story, "Problem")
    add_list(story, prior_paper.get("problem"))

    add_heading(story, "Core Techniques (P)")
    add_numbered(story, ids["P"])

    add_heading(story, "Limitations")
    add_list(story, prior_paper.get("limitations"))

    add_heading(story, "Experiment Results (R-P)")
    add_numbered(story, ids["RP"])


##################################################
# Compare Input 생성
##################################################

def create_compare_input(my_paper, prior_paper, output_pdf, font_path=None):
    """
    my_paper + prior_paper (dict 또는 JSON 경로)
            ↓
    Compare_Input.pdf 생성, 번호(ids) 반환
    """

    print("Compare Input PDF 생성...")

    my_paper = _as_dict(my_paper)
    prior_paper = _as_dict(prior_paper)

    ids = assign_ids(my_paper, prior_paper)

    register_font(font_path)

    story = []

    add_guide(story)
    story.append(PageBreak())

    add_my_paper(story, my_paper, ids)
    story.append(Spacer(1, 1 * cm))

    add_prior_paper(story, prior_paper, ids)

    Path(output_pdf).parent.mkdir(parents=True, exist_ok=True)

    create_document(output_pdf).build(story)

    print(
        f"M {len(ids['M'])}개, P {len(ids['P'])}개, "
        f"R-M {len(ids['RM'])}개, R-P {len(ids['RP'])}개"
    )

    print(f"저장 완료: {output_pdf}")

    return ids


if __name__ == "__main__":

    if len(sys.argv) != 4:
        print("사용법: python compare_builder.py my_paper.json prior_paper.json Compare_Input.pdf")
        sys.exit(1)

    create_compare_input(*sys.argv[1:])
