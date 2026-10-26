"""
resume_agent.py

Resume Agent 실행 모듈

- Resume Agent 생성
- Resume 분석 요청
"""

from config import (
    RESUME_AGENT_ID,
    RESUME_CONFIG_ID
)

from agent_client import (
    AgentClient
)

##################################################
# Resume Agent
##################################################

resume_agent = AgentClient(

    agent_id=RESUME_AGENT_ID,

    config_id=RESUME_CONFIG_ID

)

##################################################
# Resume 분석
##################################################

def analyze_resume(
    file_id: str
) -> dict:
    """
    Resume Agent 실행

    Parameters
    ----------
    file_id : str
        Files API에서 업로드한 File ID

    Returns
    -------
    dict
        Resume 분석 결과(JSON)
    """

    print("-" * 60)
    print("Resume Agent")
    print("-" * 60)

    print(f"Agent ID  : {RESUME_AGENT_ID}")
    print(f"Config ID : {RESUME_CONFIG_ID}")
    print(f"File ID   : {file_id}")
    print()

    result = resume_agent.run(
        file_id
    )

    print("Resume Analysis Complete")
    print()

    return result