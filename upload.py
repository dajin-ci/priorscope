"""
upload.py

Upstage Files API
"""

from pathlib import Path

from openai import OpenAI

from config import (
    UPSTAGE_API_KEY,
    UPSTAGE_HEADERS
)

##################################################
# OpenAI Client
##################################################

client = OpenAI(
    api_key=UPSTAGE_API_KEY,
    base_url="https://api.upstage.ai/v2",
    default_headers=UPSTAGE_HEADERS
)

##################################################
# Upload File
##################################################

def upload_file(
    file_path: str | Path
) -> str:
    """
    Files API를 이용하여 문서를 업로드한다.

    Parameters
    ----------
    file_path : str | Path

    Returns
    -------
    str
        업로드된 File ID
    """

    file_path = Path(file_path)

    if not file_path.exists():

        raise FileNotFoundError(
            f"{file_path} 파일이 존재하지 않습니다."
        )

    print("Uploading...")
    print(file_path)

    with open(file_path, "rb") as f:

        uploaded_file = client.files.create(

            file=f,

            purpose="user_data"

        )

    print()
    print("Upload Complete")
    print(f"File ID : {uploaded_file.id}")

    return uploaded_file.id
