"""
config.py

Project 2. HR AI Service

프로젝트 환경설정
"""

import os
from pathlib import Path

from dotenv import load_dotenv

##################################################
# Load Environment
##################################################

load_dotenv()

##################################################
# Upstage API
##################################################

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")

# 에이전트가 Studio 프로젝트 안에 있으면 업로드·실행·폴링에 같은 프로젝트 ID를 붙여야 한다.
# 비어 있으면 헤더를 보내지 않는다 (개인 공간 에이전트용).
UPSTAGE_PROJECT_ID = os.getenv("UPSTAGE_PROJECT_ID")

UPSTAGE_HEADERS = (
    {"x-project-id": UPSTAGE_PROJECT_ID}
    if UPSTAGE_PROJECT_ID
    else {}
)

##################################################
# My Paper Agent (스타터의 Resume 자리)
##################################################

RESUME_AGENT_ID = os.getenv("MY_PAPER_AGENT_ID")
RESUME_CONFIG_ID = os.getenv("MY_PAPER_CONFIG_ID")

##################################################
# Prior Paper Agent (스타터의 JD 자리)
##################################################

JD_AGENT_ID = os.getenv("PRIOR_PAPER_AGENT_ID")
JD_CONFIG_ID = os.getenv("PRIOR_PAPER_CONFIG_ID")

##################################################
# Compare Agent (스타터의 Matching 자리)
##################################################

MATCHING_AGENT_ID = os.getenv("COMPARE_AGENT_ID")
MATCHING_CONFIG_ID = os.getenv("COMPARE_CONFIG_ID")

##################################################
# Project Directory
##################################################

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

OUTPUT_DIR = BASE_DIR / "output"

RESULT_DIR = BASE_DIR / "result"

##################################################
# Input Files
##################################################

RESUME_FILE = DATA_DIR / "My_Paper.pdf" # 내 논문 

JD_FILE = DATA_DIR / "Prior_Paper.pdf" # 기존 논문 

##################################################
# Output Files
##################################################

RESUME_JSON = OUTPUT_DIR / "my_paper.json"

JD_JSON = OUTPUT_DIR / "prior_paper.json"

MATCHING_PDF = OUTPUT_DIR / "Compare_Input.pdf"

MATCHING_RESULT = RESULT_DIR / "compare_result.json"

VALIDATED_RESULT = RESULT_DIR / "validated_result.json" 


##################################################
# fonts
##################################################

FONT_NAME = "Nanum"

FONT_PATH = BASE_DIR / "fonts" / "NanumGothic-Regular.ttf"


##################################################
# Directory Initialization
##################################################

def create_directories():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

##################################################
# Configuration Validation
##################################################

def validate_config():

    required = {

        "UPSTAGE_API_KEY": UPSTAGE_API_KEY,

        "MY_PAPER_AGENT_ID": RESUME_AGENT_ID,
        "MY_PAPER_CONFIG_ID": RESUME_CONFIG_ID,

        "PRIOR_PAPER_AGENT_ID": JD_AGENT_ID,
        "PRIOR_PAPER_CONFIG_ID": JD_CONFIG_ID,

        "COMPARE_AGENT_ID": MATCHING_AGENT_ID,
        "COMPARE_CONFIG_ID": MATCHING_CONFIG_ID,

    }

    missing = [

        key

        for key, value in required.items()

        if not value

    ]

    if missing:

        raise ValueError(

            "다음 환경변수가 설정되지 않았습니다.\n\n"

            + "\n".join(missing)

        )

    create_directories()

##################################################
# Project Information
##################################################

def print_config():

    print("=" * 60)
    print("Project Configuration")
    print("=" * 60)

    print(f"Project Directory : {BASE_DIR}")
    print(f"Data Directory    : {DATA_DIR}")
    print(f"Output Directory  : {OUTPUT_DIR}")
    print(f"Result Directory  : {RESULT_DIR}")

    print()

    print(f"My Paper Agent    : {RESUME_AGENT_ID}")
    print(f"My Paper Config   : {RESUME_CONFIG_ID}")

    print(f"Prior Paper Agent : {JD_AGENT_ID}")
    print(f"Prior Paper Config: {JD_CONFIG_ID}")

    print(f"Compare Agent     : {MATCHING_AGENT_ID}")
    print(f"Compare Config    : {MATCHING_CONFIG_ID}")

    print(f"Project ID        : {UPSTAGE_PROJECT_ID or '(없음)'}")

    print("=" * 60)
