"""
matching_agent.py

Matching Agent 실행
"""

from config import (
    MATCHING_AGENT_ID,
    MATCHING_CONFIG_ID
)

from agent_client import (
    AgentClient
)

##################################################
# Agent 생성
##################################################

matching_agent = AgentClient(

    agent_id=MATCHING_AGENT_ID,

    config_id=MATCHING_CONFIG_ID
)


##################################################
# Matching 분석
##################################################

def analyze_matching(file_id: str) -> dict:

    print("-" * 60)
    print("Matching Agent")
    print("-" * 60)

    print(f"Agent ID  : {MATCHING_AGENT_ID}")
    print(f"Config ID : {MATCHING_CONFIG_ID}")
    print(f"File ID   : {file_id}")

    print()

    result = matching_agent.run(
        file_id
    )

    print("Matching Analysis Complete")

    print()

    return result