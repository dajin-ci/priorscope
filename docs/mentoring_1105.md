# 멘토링 11/05 반영

## 반영한 것

| 멘토링 항목 | 반영 | 파일 |
|---|---|---|
| 새로고침하면 PDF가 사라짐 | 업로드할 때 `runs/<run_id>/`에 저장하고 주소에 `?run=<run_id>`를 붙임. 새로고침하면 업로드 파일·진행 단계·결과를 다시 읽음 | run_storage.py, streamlit_app.py |
| 진행 중에도 [비교 시작]을 또 누를 수 있음 | 분석을 화면과 분리된 스레드에서 실행하고 `run.lock`으로 막음. 진행 중에는 버튼·업로드·관심 초점이 잠기고, 2초마다 진행 단계를 갱신 | service.py (`start_in_background`), streamlit_app.py |
| PDF 몇 쪽까지 되는지 | `bench_pages.py`로 측정. Studio 대기에 최대 시간(`AGENT_MAX_WAIT`, 기본 180초) 추가 | bench_pages.py, agent_client.py |
| Studio에 의존하지 않기 | 이번에는 진행하지 않음 (2차) | - |
| 겹치는 요소에서 얻는 인사이트 | 겹침 칸에 인용할 기존 논문 절, 내 쪽의 차이, 서술 방식, 예상 리뷰어 질문 표시 | streamlit_app.py, insight_agent.py |
| A→B, B→C 관계 | 8단계 관계 분석 (확장·보완·상충·연결). '연결'은 항상 추론으로 표시 | insight_agent.py |
| 샘플 결과가 FAILED로 표시됨 | Studio가 단일 값 필드에 같은 값을 반복해 낸 경우(overlap_level ×3 등) 하나로 합치고 info로 기록. 값이 다르면 기존대로 오류. 샘플을 v11 S2 원출력으로 현재 코드에서 다시 검증 | validator.py, samples/ |
| 비교할 실험이 없으면 FAILED | Compare Agent가 result_pairs에 "해당 없음"을 쓰면 빈 목록으로 처리, summary·related_work_draft가 여러 문장으로 나뉘면 이어 붙임 (모두 info로 기록). 저장된 FAILED 4건(v9 S1, v10 S4, v11 S1·S2)이 판정 변화 없이 해소 | validator.py |
| "부족한 점" 어감 | "보완을 검토할 지점 (기존 논문 대비)"로 변경 | streamlit_app.py |
| 관심 분야 반영 | 체크박스(측면 6개, 얻고 싶은 것 3개). Compare_Input.pdf 안내문과 관계 분석 프롬프트에 들어감. 대응 판정·등급에는 영향 없음 | focus.py, compare_builder.py |
| 대주제가 다른데 내용이 같은 경우 | 이번에는 진행하지 않음 (2차) | - |

## 환경변수 (Railway Variables)

| 이름 | 기본값 | 설명 |
|---|---|---|
| `AGENT_MAX_WAIT` | 180 | Studio Job 최대 대기(초). bench 결과로 조정 |
| `PAGE_WARN` / `PAGE_MAX` | 20 / 40 | 업로드 안내 기준 쪽수 (임시값, bench 결과로 조정) |
| `INSIGHT_MODEL` | (비움) | 8단계 관계 분석 모델. 비우면 8단계를 건너뜀. 예: `solar-pro4` |

## 한계

- Railway 디스크는 재배포·재시작하면 비워진다. 새로고침은 버티지만 재배포 후에는 이전 run 주소가 열리지 않는다.
- 실행 중 서버가 재시작되면 화면은 "중단됨"으로 표시하고 다시 시작하게 한다.
- lock은 같은 서버 안에서만 유효하다. Railway 인스턴스를 1개로 둔다.
- run 주소를 아는 사람은 결과를 볼 수 있다 (로그인 없음, 1차 범위 밖). 공유하지 말고, 끝나면 삭제 버튼을 쓰도록 안내한다.

## 샘플 결과 보기: 경로별 사례 (11/06)

실제로 돌린 평가 결과로 경우별 화면을 미리 만들어 둔다. API를 부르지 않는다.
`python eval/build_samples.py` 로 다시 만들며, 비교까지 간 사례는 현재 validator 규칙으로 다시 검증한다.

| 사례 | 경로 | 출처 |
|---|---|---|
| 연구 내용 비교 (RoBERTa ↔ BERT) | research | v11/S2 |
| 공통 범위만 비교 · 국문↔영문 | partial | v11/S4 |
| 공통 범위만 비교 · 방법 연결 (OV-AVEL ↔ ImageBind) | partial | v11/S1 |
| 비교 부적합 (DETR ↔ Conformer) | unsuitable | v11/S3 |
| 비교 부적합 · 논문이 아닌 문서 (A100 백서 ↔ BERT) | unsuitable | v11/S5 |
| 판단 보류 | insufficient | v7/S1 (적합성 v1 시절) |

method(방법론 중심 비교) 경로는 실제로 나온 실행이 없어 사례가 없다. 해당 쌍을 한 번 돌리면 CASES에 추가한다.
