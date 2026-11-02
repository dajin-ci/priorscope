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

## 경로 라벨을 축으로 받는 이유

라벨러가 경로를 바로 고르면 "그 경로가 맞는가"와 "경로 규칙이 맞는가"를 구분할 수 없다. 그래서 세 축(문제·범위·방법)의 관계만 받고, 경로는 `suitability.select_route` 와 같은 함수로 계산한다. 덕분에 모델이 어느 축을 틀렸는지 축 단위로 볼 수 있다.

대신 `route_intuition` 에 규칙을 떠올리지 않은 직감 경로를 함께 받는다. 계산 경로와 직감이 자주 어긋나면 모델이 아니라 `select_route` 규칙을 고쳐야 한다는 신호다. merge 가 어긋난 라벨러를 "규칙 점검 필요"로 출력한다.

## 의견이 갈렸을 때

축 관계가 갈려도 계산 경로가 같으면 그 경로가 정답이다. 계산 경로까지 갈리면 `expected_route` 는 비우고 `acceptable_routes` 에 모두 남기며 `disputed: true` 로 표시한다. 평가에서는 확정 경로 샘플과 분리해 집계한다(설계서의 "보류는 별도 집계"와 같은 원칙). `comparison_expected` 는 라벨러 전원이 "비교 진행" 또는 "비교 차단"에 동의할 때만 true/false 이고, 그래야 게이트 누수·과잉 차단 계산에 쓴다.
