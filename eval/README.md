# 평가 라벨 체계

10/31 적합성 분기 이후 평가는 두 층으로 나뉜다.

| 층 | 정답 파일 | 언제 필요한가 | 무엇을 재나 |
|---|---|---|---|
| 경로 | `route_label.json` | 모든 샘플 | 경로 정확도, 게이트 누수(막혀야 할 쌍이 비교로 감), 과잉 차단(비교해야 할 쌍이 막힘) |
| 요소 | `labels.json` | 정답 경로가 research·partial·method 일 때 | 허위 신규 주장률, 요소 대응 정확도, 임베딩 임계값 보정 |

샘플 정의와 각 샘플의 의도는 `samples/manifest.json` 에 있다. `design_intent` 는 그 샘플로 무엇을 시험하려는지일 뿐 정답이 아니다. 라벨러는 manifest 와 LLM 결과(`compare_result.json`, `suitability.json`)를 보지 않고 라벨링한다. 예외는 `label_mode: designed` 인 S5 로, 논문이 아닌 문서라 정답(비교 미진행)이 설계로 정해진다.

## 작업 순서

```
python eval/labeling.py template S2 강다진 이건영   # label_sheet.md, labels_<이름>.json, route_<이름>.json 생성
# 각자 route_<이름>.json 을 채운다 (세 축 관계 + 직감 경로)
# 정답 경로가 비교 경로일 것 같으면 labels_<이름>.json 도 채운다
python eval/labeling.py merge S2                    # route_label.json, labels.json 생성
```

이미 양식이 있는 샘플에 template 을 다시 돌려도 기존 라벨 파일은 덮어쓰지 않는다. S1 처럼 label_sheet.md 만 있던 샘플도 다시 돌리면 경로 라벨 기준과 문제·기여 목록이 시트에 추가된다.

## 실제 관계와 시트 기준 관계

경로 라벨의 축마다 `relation`(원문까지 알고 내린 실제 관계, 정답)과 `relation_from_sheet`(label_sheet.md 만 읽었을 때의 관계)를 함께 적는다. 적합성 모델은 시트와 같은 추출본만 보기 때문에, 시트만으로는 연결이 안 보이면 모델이 완벽하게 판단해도 틀린다. merge 는 두 값이 다른 축을 "추출 공백"으로, 시트 기준 경로가 실제 경로와 다른 샘플을 `route_changed_by_extraction: true` 로 표시한다. 평가에서는 모델 결과를 실제 경로와 비교해 전체 정확도를, 시트 기준 경로와 비교해 판단 단계만의 정확도를 따로 낸다.

## 임시 라벨 (provisional)

라벨러가 한 명뿐일 때는 `merge S1 --provisional` 로 임시로 합칠 수 있다. 이때 `label_status.json` 에 `provisional: true` 와 라벨러 이름이 남고, 평가 결과에도 임시 라벨 기준이라고 표시해야 한다. 빈 양식(판정을 하나도 채우지 않은 파일)은 라벨러 수에 넣지 않는다. 사람 두 명이 라벨을 채운 뒤 `--provisional` 없이 merge 하면 정답 파일과 `label_status.json` 이 교체된다. 이때 `route_claude.json`, `labels_claude.json` 처럼 LLM 라벨 파일이 폴더에 남아 있으면 라벨러로 함께 합쳐지므로, 사람 라벨만으로 정답을 만들려면 먼저 `eval/samples/<샘플>/llm/` 같은 하위 폴더로 옮긴다.

현재 S1, S2 의 정답은 Claude 가 만든 임시 라벨이다 (2026-11-02).

## 경로 라벨을 축으로 받는 이유

라벨러가 경로를 바로 고르면 "그 경로가 맞는가"와 "경로 규칙이 맞는가"를 구분할 수 없다. 그래서 세 축(문제·범위·방법)의 관계만 받고, 경로는 `suitability.select_route` 와 같은 함수로 계산한다. 덕분에 모델이 어느 축을 틀렸는지 축 단위로 볼 수 있다.

대신 `route_intuition` 에 규칙을 떠올리지 않은 직감 경로를 함께 받는다. 계산 경로와 직감이 자주 어긋나면 모델이 아니라 `select_route` 규칙을 고쳐야 한다는 신호다. merge 가 어긋난 라벨러를 "규칙 점검 필요"로 출력한다.

## 의견이 갈렸을 때

축 관계가 갈려도 계산 경로가 같으면 그 경로가 정답이다. 계산 경로까지 갈리면 `expected_route` 는 비우고 `acceptable_routes` 에 모두 남기며 `disputed: true` 로 표시한다. 평가에서는 확정 경로 샘플과 분리해 집계한다(설계서의 "보류는 별도 집계"와 같은 원칙). `comparison_expected` 는 라벨러 전원이 "비교 진행" 또는 "비교 차단"에 동의할 때만 true/false 이고, 그래야 게이트 누수·과잉 차단 계산에 쓴다.

## 에이전트 스키마에 필드를 추가했을 때

샘플을 통째로 다시 추출하면 core_techniques 순서가 바뀌어 M·P 번호와 요소 라벨이 어긋난다. 새 필드만 고정본에 끼워 넣는다.

```
python eval/add_fields.py S1 prior ~/papers/ImageBind.pdf contributions
```

번호를 만드는 `core_techniques`, `experiment_results` 는 거부한다. 새 추출본 전체는 `reextract_prior_paper.json` 으로 남고, 끝나면 label_sheet.md 가 다시 만들어진다.

## 평가 실행 (evaluate.py)

```
python eval/evaluate.py compare --tag v7            # 고정 추출본으로 3~7단계 실행 후 채점 (API 사용)
python eval/evaluate.py score eval/results/v7       # 저장된 결과 재채점 (API 없음)
python eval/evaluate.py stability --pdf-dir ~/papers --runs 3 S1 S2   # PDF로 전체를 N번, 흔들림 측정
```

compare 는 `service.run_from_extracted` 를 그대로 호출하므로 실제 서비스와 같은 코드 경로를 평가한다. 결과는 `eval/results/<tag>/<샘플>/` 에 실행 폴더와 같은 파일로 남고 `report.json` 이 함께 만들어진다. 라벨을 고친 뒤에는 API 를 다시 부르지 않고 score 만 돌리면 된다. stability 의 PDF 이름은 `S1_my.pdf`, `S1_prior.pdf` 형식이다.

| 지표 | 뜻 | 목표 |
|---|---|---|
| false_novelty_rate | 정답이 일치·유사인 M 중 최종 판정이 없음인 비율 (주 지표) | 10% 이하 |
| element_accuracy | 최종 판정이 정답과 같은 M 비율 | 80% 이상 |
| route_accuracy | 예측 경로가 정답 경로에 든 비율 (의견 갈린 샘플 제외) | 80% 이상 |
| gate_leak_rate | 비교가 막혀야 할 쌍이 비교로 넘어간 비율 | 0% |
| grade_agreement | research 정답 샘플에서 확정 등급이 기대 등급과 같은 비율 (보류는 별도) | 80% 이상 |
| route_accuracy_vs_sheet | 시트 기준 경로 대비 정확도. 실제 경로 정확도와 차이가 크면 추출 문제 | 참고 |
| false_novelty_rate_agent | 검증 전 Compare Agent 원판정의 허위 신규 주장률. 위 값과 차이가 validator 효과 | 참고 |
