# PriorScope

내 논문과 기존 논문 PDF를 올리면, 두 논문이 **비교할 수 있는 쌍인지 먼저 판단**하고 겹치는 요소·차이·보완 지점을 근거와 함께 보여주는 선행연구 비교 서비스입니다.

## 1. 서비스 소개

- **입력**: 내 논문 PDF 1개 + 기존(선행) 논문 PDF 1개
- **출력**: 적합성 판단 경로, 요소별 대응 판정, 보완을 검토할 지점, 관련 연구 초안, 논문 간 관계·인사이트
- **특징**
  - **적합성 분기**: 문제·범위·방법 세 축의 관계로 경로를 정한다 (`research` / `partial` / `method` / `unsuitable` / `insufficient`). 비교할 수 없는 쌍은 억지로 비교하지 않는다.
  - **코드 검증**: LLM 출력을 `validator.py`가 규칙으로 다시 검증하고, 임베딩 유사도를 보조 지표로 쓴다. 같은 입력을 여러 번(기본 3회) 실행해 판정이 흔들리면 "확인필요"로 둔다.
  - **관심 초점**: 측면 6개·얻고 싶은 것 3개를 체크하면 안내문과 관계 분석에 반영된다 (판정·등급에는 영향 없음).
  - **샘플 결과 보기**: API 호출 없이 경로별 사례(`samples/cases/`)를 같은 화면으로 확인한다.
  - 새로고침해도 실행이 이어지고(`?run=<run_id>`), 결과는 삭제 버튼으로 지울 수 있으며 기본 24시간 뒤 자동 정리된다.

## 2. 아키텍처

```
Streamlit UI (streamlit_app.py)          CLI (app.py)
          └──────────────┬──────────────────┘
                   service.py  (백그라운드 스레드 · run.lock · state.json)
                         │  실행마다 runs/<run_id>/ 에 저장 (run_storage.py)
   ┌─────────────────────┼──────────────────────────────────────────┐
 1 내 논문 분석      2 기존 논문 분석       3 적합성 판단 (suitability.py, 3회 합의)
 resume_agent.py     jd_agent.py                │
   (Upstage Studio Agent)               경로 분기 (research/partial/method → 4~7단계,
                                                  unsuitable/insufficient → 비교 생략)
 4 비교용 PDF 생성 (compare_builder.py, reportlab)
 5 비교 분석 (matching_agent.py, Compare Agent × COMPARE_RUNS 동시 실행)
 6 임베딩 유사도 (similarity.py)  ← 보조, 실패해도 계속
 7 코드 검증 (validator.py, verdict_rules.py)
 8 관계·인사이트 분석 (insight_agent.py)  ← 보조, INSIGHT_MODEL 설정 시
                         │
                comparison_report.py → report.json → 화면 표시
```

| 구성 | 위치 |
|---|---|
| 화면 | `streamlit_app.py` |
| 파이프라인 | `service.py`, `*_agent.py`, `suitability.py`, `validator.py`, `similarity.py` |
| 저장·정리 | `run_storage.py`, `runs/`, `output/`, `result/` |
| 에이전트 설정 | `agent_configs/` (Studio에 등록할 My Paper / Prior Paper / Compare Agent) |
| 평가 | `eval/` (라벨링·평가·샘플 생성, [eval/README.md](eval/README.md)) |
| 테스트 | `tests/` |
| 배포 | `Procfile`, `railway.json` (Railway) |

- **Python 3.11+**, Streamlit, OpenAI 호환 SDK(Upstage), reportlab, pypdf, Pillow

## 3. 실행 방법

```bash
# 1) 설치
pip install -r requirements.txt

# 2) 환경변수 설정
cp .env.example .env      # 값 채우기 (아래 4장)

# 3) 웹 화면 실행
streamlit run streamlit_app.py

# CLI 실행 (data/My_Paper.pdf, data/Prior_Paper.pdf 사용)
python app.py

# 테스트
pytest tests
```

- Upstage Studio에 `agent_configs/`의 에이전트 3개를 만들고, 발급된 ID를 `.env`에 넣어야 새 분석이 동작합니다.
- 샘플 결과 보기 탭은 API 키 없이도 볼 수 있습니다.
- 배포: Railway (`Procfile`의 `streamlit run ... --server.port $PORT`). 디스크는 재배포 시 비워지고, lock이 서버 내부에서만 유효하므로 **인스턴스 1개**로 운영합니다.

## 4. 환경변수

`.env`(로컬) 또는 Railway Variables에 설정합니다.

| 이름 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `UPSTAGE_API_KEY` | ✅ | - | Upstage API 키 |
| `UPSTAGE_PROJECT_ID` | | (없음) | Studio 프로젝트 안의 에이전트일 때 `x-project-id` 헤더로 전송 |
| `MY_PAPER_AGENT_ID` / `MY_PAPER_CONFIG_ID` | ✅ | - | 내 논문 분석 에이전트 |
| `PRIOR_PAPER_AGENT_ID` / `PRIOR_PAPER_CONFIG_ID` | ✅ | - | 기존 논문 분석 에이전트 |
| `COMPARE_AGENT_ID` / `COMPARE_CONFIG_ID` | ✅ | - | 비교 에이전트 |
| `SUITABILITY_MODEL` | | `solar-pro4` | 적합성 판단 모델 |
| `COMPARE_RUNS` | | `3` | Compare Agent 반복 실행 횟수 (판정 합의) |
| `SUITABILITY_RUNS` | | `3` | 적합성 판단 반복 횟수 |
| `INSIGHT_MODEL` | | (비움) | 8단계 관계 분석 모델. 비우면 건너뜀 (예: `solar-pro4`) |
| `EMBED_MODEL` | | `embedding-passage` | 임베딩 모델 |
| `SIMILARITY_DEMOTE_THRESHOLD` | | 코드 내 기본값 | 유사도 기반 판정 강등 임계값 |
| `AGENT_MAX_WAIT` | | `180` | Studio Job 최대 대기(초) |
| `PAGE_WARN` / `PAGE_MAX` | | `20` / `40` | 업로드 안내 기준 쪽수 |
| `RUN_RETENTION_HOURS` | | `24` | 실행 결과 보관 시간 |

## 5. API

PriorScope 자체는 REST API를 제공하지 않고 Streamlit 화면과 CLI로 동작합니다. 외부에서 사용하는 API와 내부 진입점은 다음과 같습니다.

**사용하는 외부 API (Upstage)**

| 용도 | 엔드포인트 | 코드 |
|---|---|---|
| Studio 에이전트 파일 업로드·실행·폴링 | `https://api.upstage.ai/v2` | `upload.py`, `agent_client.py` |
| 적합성 판단·관계 분석 (Chat Completions) | `https://api.upstage.ai/v1` | `suitability.py`, `insight_agent.py` |
| 임베딩 | `https://api.upstage.ai/v1` | `similarity.py` |

**내부 진입점**

| 함수 / 명령 | 설명 |
|---|---|
| `service.run_compare_service(my_pdf, prior_pdf, on_step)` | 1~8단계 동기 실행, 결과 번들 반환 |
| `service.start_in_background(...)` | 화면용 백그라운드 실행 (중복 실행 방지) |
| `python check_run.py --run-dir runs/<run_id>` | 저장된 실행 결과 점검 |
| `python revalidate.py` | API 호출 없이 코드 검증만 다시 실행 |
| `python eval/evaluate.py` · `eval/build_samples.py` | 평가 실행 · 샘플 사례 생성 |

## 6. 팀원

- 강다진
- 이건영
