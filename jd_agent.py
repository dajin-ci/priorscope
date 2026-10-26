"""
jd_agent.py

JD Agent 실행 모듈

- JD Agent 생성
- Job Description 분석 요청
"""

from config import (
    JD_AGENT_ID,
    JD_CONFIG_ID
)

from agent_client import (
    AgentClient
)

##################################################
# JD Agent
##################################################

jd_agent = AgentClient(

    agent_id=JD_AGENT_ID,

    config_id=JD_CONFIG_ID

)

##################################################
# JD 분석
##################################################

def analyze_jd(
    file_id: str
) -> dict:
    """
    JD Agent 실행

    Parameters
    ----------
    file_id : str
        Files API에서 업로드한 File ID

    Returns
    -------
    dict
        JD 분석 결과(JSON)
    """

    print("-" * 60)
    print("JD Agent")
    print("-" * 60)

    print(f"Agent ID  : {JD_AGENT_ID}")
    print(f"Config ID : {JD_CONFIG_ID}")
    print(f"File ID   : {file_id}")
    print()

    result = jd_agent.run(
        file_id
    )

    print("JD Analysis Complete")
    print()

    return result