"""
file_manager.py

파일 저장 및 로드
"""

import json

from pathlib import Path

from config import (
    FONT_NAME,
    FONT_PATH
)

##################################################
# PDF
##################################################

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import (
    getSampleStyleSheet
)

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


##################################################
# Directory
##################################################

def ensure_directory(path: Path):
    """
    폴더가 없으면 생성
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )


##################################################
# JSON
##################################################

def save_json(data: dict, file_path: Path):
    """
    JSON 저장
    """

    ensure_directory(file_path)

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )


def load_json(file_path: Path):
    """
    JSON 읽기
    """

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


##################################################
# Markdown
##################################################

def save_markdown(text: str, file_path: Path):
    """
    Markdown 저장
    """

    ensure_directory(file_path)

    with open(
        file_path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(text)


def load_markdown(file_path: Path):

    with open(
        file_path,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


##################################################
# PDF
##################################################

def save_pdf(text: str, file_path: Path):
    """
    PDF 저장
    """

    ensure_directory(file_path)

    ##################################################
    # Font
    ##################################################

    try:

        pdfmetrics.registerFont(

            TTFont(
                FONT_NAME,
                str(FONT_PATH)
            )
        )

        font_name = FONT_NAME

    except Exception:

        print("Warning : Font file not found.")
        print("Fallback to Helvetica.")

        font_name = "Helvetica"

    ##################################################
    # Style
    ##################################################

    styles = getSampleStyleSheet()

    style = styles["BodyText"]

    style.fontName = font_name

    style.leading = 18

    ##################################################
    # PDF
    ##################################################

    pdf = SimpleDocTemplate(
        str(file_path)
    )

    story = []

    for line in text.split("\n"):

        line = line.strip()

        if line == "":

            story.append(
                Spacer(1, 8)
            )

            continue

        ##################################################
        # Markdown Header 제거
        ##################################################

        if line.startswith("###"):

            line = "<b>" + line.replace("###", "").strip() + "</b>"

        elif line.startswith("##"):

            line = "<b>" + line.replace("##", "").strip() + "</b>"

        elif line.startswith("#"):

            line = "<b>" + line.replace("#", "").strip() + "</b>"

        ##################################################
        # PDF Paragraph
        ##################################################

        story.append(

            Paragraph(

                line.replace(" ", "&nbsp;"),

                style

            )

        )

    pdf.build(story)


##################################################
# PDF Load
##################################################

def load_pdf(file_path: Path):

    return file_path