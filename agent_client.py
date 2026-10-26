"""
agent_client.py

공통 Agent 실행 모듈

Resume Agent
JD Agent
Matching Agent

모든 Agent는 이 클래스를 이용하여 실행한다.
"""

import json
import time

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
# Agent Client
##################################################

class AgentClient:
    """
    Studio Agent 실행 클래스
    """

    def __init__(
        self,
        agent_id: str,
        config_id: str = "1"
    ):

        self.agent_id = agent_id
        self.config_id = config_id

    ##################################################
    # Job 생성
    ##################################################

    def create_job(
        self,
        file_id: str
    ) -> str:

        input_data = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": file_id
                    }
                ]
            }
        ]

        response = client.responses.create(

            model=self.agent_id,

            include=["last"],

            input=input_data,

            extra_body={
                "config_id": self.config_id
            }

        )

        return response.id

    ##################################################
    # Polling
    ##################################################

    def wait_until_complete(
        self,
        job_id: str,
        interval: int = 2
    ):

        response = client.responses.retrieve(

            job_id,

            include=["last"]

        )

        print(f"Status : {response.status}")

        while response.status in (
            "queued",
            "in_progress"
        ):

            time.sleep(interval)

            response = client.responses.retrieve(

                job_id,

                include=["last"]

            )

            print(f"Status : {response.status}")

        if response.status == "failed":

            raise RuntimeError(
                "Studio Agent 실행 실패"
            )

        if response.status != "completed":

            raise RuntimeError(
                f"Unknown Status : {response.status}"
            )

        print("Job Complete")

        return response

    ##################################################
    # Result Parsing
    ##################################################

    def parse_result(
        self,
        response
    ):

        if not response.output_text:

            raise ValueError(
                "output_text가 존재하지 않습니다."
            )

        try:

            result = json.loads(
                response.output_text
            )

        except json.JSONDecodeError:

            raise ValueError(
                "output_text가 JSON 형식이 아닙니다."
            )

        return result

    ##################################################
    # Agent 실행
    ##################################################

    def run(
        self,
        file_id: str
    ):

        print("-" * 60)
        print("Create Job")
        print("-" * 60)

        job_id = self.create_job(
            file_id
        )

        print(f"Job ID : {job_id}")
        print()

        print("-" * 60)
        print("Waiting...")
        print("-" * 60)

        response = self.wait_until_complete(
            job_id
        )

        print()

        print("-" * 60)
        print("Parse Result")
        print("-" * 60)

        result = self.parse_result(
            response
        )

        print("JSON Parsing Complete")

        return result
