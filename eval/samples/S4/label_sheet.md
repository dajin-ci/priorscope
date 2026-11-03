# S4 라벨 시트

- 내 논문: BERT 기반 자연어처리 모델의 미세 조정을 통한 한국어 리뷰 감성 분석: 입력 시퀀스 길이 최적화☆
- 기존 논문: How to Fine-Tune BERT for Text Classification?

## 라벨 기준 (verdict_rules.py, 2026-11-02 확정)

- 판정 기준은 '이 M을 기존 논문과 다른 점이라고 주장하면 심사자가 기존 논문에 이미 있다고 반박할 수 있는가'다.
- 일치: 기존 P를 그대로 쓰거나 같은 기법이다. 기존 논문의 사전학습 모델·인코더·임베딩 공간을 그대로 쓰는 경우도 일치다.
- 유사: 기존 P와 같은 역할을 유지한 채 방식을 변형·확장·교체했다. 예: 정적 마스킹을 동적 마스킹으로, WordPiece를 BPE로.
- 없음: 기존 논문에 없는 요소다. 기존 P를 제거한 것, 학습 규모·기간·배치·데이터 양 같은 설정값만 바꾼 것도 없음이다. 이때 P 칸은 '-'로 두고 설명에 관련 P 번호를 적는다.
- 없음: Transformer 사용, 손실 함수로 학습처럼 범용 기법 수준의 공통점만 있으면 없음이다.
- 확인필요: 위 기준으로도 판단이 서지 않으면 없음이 아니라 확인필요로 적는다.
- 같은 기술을 다른 용어나 다른 언어(국문/영문)로 쓴 경우도 대응으로 본다.

각자 따로 라벨링하고 서로의 답을 보지 않는다. LLM 결과(compare_result)도 보지 않는다.
prior 에는 대응하는 P 번호를 적는다 (일치·유사일 때만, 없으면 빈 칸).

## 경로 라벨 기준 (route_<이름>.json)

경로를 직접 고르지 말고 세 축의 관계를 고른다. 경로는 코드가 계산한다.
축마다 두 값을 적는다.
- relation: 원문 PDF까지 알고 내린 실제 관계 (정답으로 쓴다)
- relation_from_sheet: 이 시트만 읽었을 때의 관계 (모델이 보는 자료와 같다)
시트만 읽으면 달라 보이지만 원문을 알면 연결되는 경우, 두 값을 다르게 적고 memo 에 이유를 남긴다.

- problem (해결 문제·목적)
  - same: 같은 문제를 푼다 / related: 연관되지만 다른 문제 / different: 연결 없음 / unknown: 판단 불가
  - 분야 이름이나 키워드가 같다는 이유만으로 same 을 고르지 않는다.
- scope (연구 범위·대상: 입출력, 연구 대상, 전제 조건)
  - comparable: 연구 내용을 견줄 수 있을 만큼 대응 / partial: 일부만 공통 / different: 다름 / unknown
  - 실험 조건이 같은지와는 별개다.
- method (핵심 방법)
  - specific_shared: 구체적 기법·모듈·학습 절차를 공유·변형·확장
  - generic_only: Transformer, 딥러닝 같은 범용 기반만 공통 / different: 연결 없음 / unknown
- route_intuition: 규칙을 떠올리지 말고 직감으로 고른 경로
  (research, partial, method, unsuitable, insufficient 중 하나)

경로 계산 규칙 (suitability.select_route):
problem=same 이고 scope=comparable → research, scope=partial·different → partial /
problem=related 이고 scope 판단 가능 → partial /
problem=different 이고 method=specific_shared → method, generic_only·different → unsuitable /
그 밖 → insufficient

## 내 논문 problem

- 리뷰 데이터는 종종 부정확하거나 불균형을 이루는 만족도 점수 분포와 텍스트의 다양성으로 인해 분석에 어려움을 겪는다[4].
- 텍스트에는 부정적인 내용이 내포되어 있음에도 구매 만족도 값은 긍정으로 매겨져 있는 경우가 다수 존재한다.
- 긍정적인 리뷰와 부정적인 리뷰의 큰 불균형은 추후의 분석 결과를 방해하기 때문에 불균형 완화가 필요하다.
- 메모리 효율을 고려할 때 64를 가장 최적의 길이로 판단하였다.

## 내 논문 contributions

- [1] 한국어 의류 쇼핑 플랫폼 리뷰 데이터를 수집하고 GPT-4 API로 구매 만족도 라벨 값을 재조정한다.
- [1] 입력 시퀀스 길이에 따라 BERT 기반 다양한 사전학습 모델을 한국어 리뷰에 대해 미세 조정한다.
- [1] 한국어 의류 쇼핑 플랫폼에서 최적의 BERT 기반 모델과 입력 시퀀스 길이를 탐구한다.
- [1] 새로 입력되는 리뷰의 카테고리를 나누고, 리뷰의 감성 점수를 산출하는 프로세스를 제공한다.

## 내 논문 experiment_results

- ? | Price | ? | single | 없음 | Result | 75.88% negative | ↓ | [Table 4]
- ? | Design | ? | single | 없음 | Result | 80.52% positive | ↑ | [Table 4]
- ? | Delivery | ? | single | 없음 | Result | 66.49% negative | ↓ | [Table 4]
- ? | Color | ? | single | 없음 | Result | 81.90% positive | ↑ | [Table 4]
- ? | Material | ? | single | 없음 | Result | 79.00% positive | ↑ | [Table 4]
- ? | Fit | ? | single | 없음 | Result | 76.10% positive | ↑ | [Table 4]

## 기존 논문 problem

- Although BERT has achieved amazing results in many natural language understanding (NLU) tasks, its potential has yet to be fully explored.
- There is little research to enhance BERT to improve the performance on target tasks further.
- The first problem of applying BERT to text classification is how processing the text with a length larger than 512.
- Catastrophic forgetting (McCloskey and Cohen, 1989) is usually a common problem in transfer learning, which means the pre-trained knowledge is erased during learning of new knowledge.

## 기존 논문 contributions

- [1] We propose a general solution to fine-tune the pre-trained BERT model, which includes three steps: (1) further pre-train BERT on within-task training data or in-domain data; (2) optional fine-tuning BERT with multi-task learning if several related tasks are available; (3) fine-tune BERT for the target task. We also investigate the fine-tuning methods for BERT on target task, including preprocess of long text, layer selection, layer-wise learning rate, catastrophic forgetting, and low-shot learning problems. We achieve the new state-of-the-art results on seven widely-studied English text classification datasets and one Chinese news classification dataset.

## 기존 논문 limitations

- (추출되지 않음)

## 기존 논문 experiment_results

- IMDb | BERT-Feat | test | single | 없음 | error rate (%) | 6.79 | ↓ | [Table 6]
- Yelp P. | BERT-Feat | test | single | 없음 | error rate (%) | 2.39 | ↓ | [Table 6]
- Yelp F. | BERT-Feat | test | single | 없음 | error rate (%) | 30.47 | ↓ | [Table 6]
- TREC | BERT-Feat | test | single | 없음 | error rate (%) | 4.20 | ↓ | [Table 6]
- Yah. A. | BERT-Feat | test | single | 없음 | error rate (%) | 22.72 | ↓ | [Table 6]
- AG | BERT-Feat | test | single | 없음 | error rate (%) | 5.92 | ↓ | [Table 6]
- DBP | BERT-Feat | test | single | 없음 | error rate (%) | 0.70 | ↓ | [Table 6]
- Sogou | BERT-Feat | test | single | 없음 | error rate (%) | 2.50 | ↓ | [Table 6]
- IMDb | BERT-FiT | test | single | 없음 | error rate (%) | 5.40 | ↓ | [Table 6]
- Yelp P. | BERT-FiT | test | single | 없음 | error rate (%) | 2.28 | ↓ | [Table 6]
- Yelp F. | BERT-FiT | test | single | 없음 | error rate (%) | 30.06 | ↓ | [Table 6]
- TREC | BERT-FiT | test | single | 없음 | error rate (%) | 2.80 | ↓ | [Table 6]
- Yah. A. | BERT-FiT | test | single | 없음 | error rate (%) | 22.42 | ↓ | [Table 6]
- AG | BERT-FiT | test | single | 없음 | error rate (%) | 5.25 | ↓ | [Table 6]
- DBP | BERT-FiT | test | single | 없음 | error rate (%) | 0.71 | ↓ | [Table 6]
- Sogou | BERT-FiT | test | single | 없음 | error rate (%) | 2.43 | ↓ | [Table 6]
- IMDb | BERT-ITPT-FiT | test | single | IMDb | error rate (%) | 4.37 | ↓ | [Table 6]
- Yelp P. | BERT-ITPT-FiT | test | single | Yelp P. | error rate (%) | 1.92 | ↓ | [Table 6]
- Yelp F. | BERT-ITPT-FiT | test | single | Yelp F. | error rate (%) | 29.42 | ↓ | [Table 6]
- TREC | BERT-ITPT-FiT | test | single | TREC | error rate (%) | 3.20 | ↓ | [Table 6]
- Yah. A. | BERT-ITPT-FiT | test | single | Yah. A. | error rate (%) | 22.38 | ↓ | [Table 6]
- AG | BERT-ITPT-FiT | test | single | AG | error rate (%) | 4.80 | ↓ | [Table 6]
- DBP | BERT-ITPT-FiT | test | single | DBP | error rate (%) | 0.68 | ↓ | [Table 6]
- Sogou | BERT-ITPT-FiT | test | single | Sogou | error rate (%) | 1.93 | ↓ | [Table 6]
- IMDb | BERT-IDPT-FiT | test | single | all sentiment | error rate (%) | 4.88 | ↓ | [Table 6]
- Yelp P. | BERT-IDPT-FiT | test | single | all sentiment | error rate (%) | 1.87 | ↓ | [Table 6]
- Yelp F. | BERT-IDPT-FiT | test | single | all sentiment | error rate (%) | 29.25 | ↓ | [Table 6]
- TREC | BERT-IDPT-FiT | test | single | all question | error rate (%) | 2.20 | ↓ | [Table 6]
- Yah. A. | BERT-IDPT-FiT | test | single | all question | error rate (%) | 21.86 | ↓ | [Table 6]
- AG | BERT-IDPT-FiT | test | single | all topic | error rate (%) | 4.88 | ↓ | [Table 6]
- DBP | BERT-IDPT-FiT | test | single | all topic | error rate (%) | 0.65 | ↓ | [Table 6]
- IMDb | BERT-CDPT-FiT | test | single | all | error rate (%) | 5.18 | ↓ | [Table 6]
- Yelp P. | BERT-CDPT-FiT | test | single | all | error rate (%) | 1.97 | ↓ | [Table 6]
- Yelp F. | BERT-CDPT-FiT | test | single | all | error rate (%) | 29.20 | ↓ | [Table 6]
- TREC | BERT-CDPT-FiT | test | single | all | error rate (%) | 2.80 | ↓ | [Table 6]
- Yah. A. | BERT-CDPT-FiT | test | single | all | error rate (%) | 21.94 | ↓ | [Table 6]
- AG | BERT-CDPT-FiT | test | single | all | error rate (%) | 5.08 | ↓ | [Table 6]
- DBP | BERT-CDPT-FiT | test | single | all | error rate (%) | 0.67 | ↓ | [Table 6]
- IMDb | + ITPT | test | single | IMDb | error rate (%) | 4.21 | ↓ | [Table 8]
- Yelp P. | + ITPT | test | single | Yelp P. | error rate (%) | 1.81 | ↓ | [Table 8]
- Yelp F. | + ITPT | test | single | Yelp F. | error rate (%) | 28.62 | ↓ | [Table 8]
- AG | + ITPT | test | single | AG | error rate (%) | 4.66 | ↓ | [Table 8]
- DBP | + ITPT | test | single | DBP | error rate (%) | 0.61 | ↓ | [Table 8]

## 내 논문 요소 (M)

- **M1** [3.1.1] Python 언어와 Selenium, BeautifulSoup 라이브러리 등을 활용하여 웹 스크래핑을 진행한다. | Python, Selenium, BeautifulSoup를 이용해 리뷰 데이터를 수집하는 웹 스크래핑 절차
- **M2** [3.1.2] GPT-4의 API를 사용하여 진행한다. | GPT-4 API로 구매 만족도 라벨을 재조정하는 절차
- **M3** [3.1.2] 긍정과 부정의 비율을 약 6:4로 설정하여 긍정 리뷰의 개수를 그 비율에 맞게 랜덤하게 삭제하는 작업을 진행한다. | 데이터 불균형 완화를 위해 언더샘플링으로 6:4 비율을 맞추는 절차
- **M4** [3.2.1] 16, 32, 64, 128으로 설정하여 결과를 비교한다. | 입력 시퀀스 길이를 여러 값으로 설정해 성능과 효율을 비교하는 방법
- **M5** [3.2.2] klue/bert, klue/roberta, kykim/albert-kor*, beomi/kcbert**, beomi/KcELECTRA* *** 모델 | 5개의 한국어 BERT 계열 사전학습 모델을 미세 조정 대상으로 사용
- **M6** [3.3] BERTopic[18]을 사용하여 토픽 모델링을 진행한다. | BERTopic으로 리뷰 카테고리를 분류하는 토픽 모델링
- **M7** [3.3] 엘보우 방법(Elbow Method)으로 토픽의 개수를 선정한다. | 토픽 수를 엘보우 방법으로 결정하는 절차
- **M8** [3.3] Okt 형태소 분석기****를 사용하여 | Okt 형태소 분석기로 명사를 추출해 카테고리별 키워드 사전을 구축
- **M9** [3.4] sotfmax 함수를 활용하여 구한다. | Softmax로 부정/긍정 확률을 계산해 감성 점수를 산출

## 기존 논문 요소 (P)

- **P1** [4.2] Within-task pre-training | 타깃 과제의 학습 데이터로 BERT를 추가 사전학습하는 방법
- **P2** [4.2] In-domain pre-training | 동일 도메인의 데이터로 BERT를 추가 사전학습하는 방법
- **P3** [4.2] Cross-domain pre-training | 동일 및 다른 도메인의 데이터를 함께 사용해 추가 사전학습하는 방법
- **P4** [4.3] Multi-task Fine-Tuning | 여러 관련 과제를 동시에 학습하면서 BERT를 멀티태스크 방식으로 미세조정하는 방법
- **P5** [4.1] head+tail | 긴 문서에서 앞 128개와 뒤 382개 토큰을 선택하는 절단 방식
- **P6** [4.1] layer-wise learning rate | 하위 층에 더 작은 학습률을 적용하는 층별 감소 학습률
