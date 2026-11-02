# S2 라벨 시트

- 내 논문: RoBERTa: A Robustly Optimized BERT Pretraining Approach
- 기존 논문: BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding

## 라벨 기준

- 일치: 기존 논문에 같은 기법이 있다 (용어·언어가 달라도 같은 것)
- 유사: 기존 논문의 핵심 아이디어를 가져다 쓰거나 변형했다
- 없음: 기존 논문에 없다. Transformer 사용, 손실 함수 학습처럼 흔한 기법만 같으면 없음
- 확인필요: 논문을 다시 봐도 판단이 어렵다

각자 따로 라벨링하고 서로의 답을 보지 않는다. LLM 결과(compare_result)도 보지 않는다.
prior 에는 대응하는 P 번호를 적는다 (일치·유사일 때만, 없으면 빈 칸).

## 경로 라벨 기준 (route_<이름>.json)

경로를 직접 고르지 말고 세 축의 관계를 고른다. 경로는 코드가 계산한다.
아래 문제·기여·요소 목록을 보고 판단하되, 애매하면 원문 PDF를 확인한다.

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

- Language model pretraining methods are hard to compare carefully because training is computationally expensive, often uses private datasets of different sizes, and final results are highly sensitive to hyperparameter choices.
- It is challenging to determine which aspects of existing self-training methods contribute the most because tuning is limited by computational cost and training data varies in size across methods.
- BERT was significantly undertrained, making later reported improvements difficult to interpret relative to training procedure and data effects.
- Previously overlooked design choices raise questions about the source of recently reported improvements in post-BERT methods.

## 내 논문 contributions

- [1] We present a set of important BERT design choices and training strategies and introduce alternatives that lead to better downstream task performance.
- [1] We use a novel dataset, CC-NEWS, and confirm that using more data for pretraining further improves performance on downstream tasks.
- [1] Our training improvements show that masked language model pretraining, under the right design choices, is competitive with all other recently published methods.

## 기존 논문 problem

- Current pre-trained language representation methods rely on unidirectional language models in both feature-based and fine-tuning approaches, which restricts the power of the learned representations.
- Standard language models are unidirectional, limiting the architectures that can be used during pre-training and preventing effective use of both left and right context.
- Left-to-right self-attention in prior models is sub-optimal for sentence-level tasks and harmful for token-level tasks such as question answering that require bidirectional context.

## 기존 논문 limitations

- [3.1] a downside is that we are creating a mismatch between pre-training and fine-tuning, since the [MASK] token does not appear during fine-tuning.
- [5.3] not all tasks can be easily represented by a Transformer encoder architecture, and therefore require a task-specific model architecture to be added.

## 내 논문 요소 (M)

- **M1** [1] training the model longer, with bigger batches, over more data | 더 오래, 더 큰 배치로, 더 많은 데이터에서 학습하는 절차
- **M2** [1] removing the next sentence prediction objective | NSP 목적함수를 제거하는 방법
- **M3** [1] training on longer sequences | 더 긴 시퀀스로 학습하는 방법
- **M4** [1] dynamically changing the mask-ing pattern applied to the training data | 학습 데이터에 적용되는 마스킹 패턴을 동적으로 바꾸는 방법
- **M5** [5] dynamic mask-ing | 동적 마스킹
- **M6** [5] FULL-SENTENCES without NSP loss | NSP 손실 없이 FULL-SENTENCES 입력 형식을 사용하는 방법
- **M7** [5] large mini-batches | 대규모 미니배치 학습
- **M8** [5] a larger byte-level BPE | 더 큰 byte-level BPE 어휘 체계
- **M9** [1] CC-NEWS | 새로 수집한 대규모 뉴스 데이터셋을 추가하는 방법

## 기존 논문 요소 (P)

- **P1** [3.1] "masked language model" (MLM) pre-training objective | 입력 토큰 일부를 마스킹하고 문맥으로 원래 토큰을 예측하도록 학습하는 양방향 사전학습 목표
- **P2** [3.1] "next sentence prediction" task | 두 문장 관계를 이해하도록 다음 문장 여부를 이진 분류로 함께 사전학습하는 절차
- **P3** [3] multi-layer bidirectional Transformer encoder | 양방향 self-attention을 사용하는 Transformer 인코더를 기본 구조로 사용
- **P4** [3.2] fine-tune all the parameters end-to-end | 다운스트림 작업에서 동일한 사전학습 파라미터로 초기화한 뒤 전체 파라미터를 종단간 미세조정
- **P5** [3] unified architecture across different tasks | 다양한 다운스트림 과제에서 거의 동일한 구조를 유지하는 통합 아키텍처
- **P6** [3] WordPiece embeddings | 30,000개 어휘의 WordPiece 임베딩을 입력 표현으로 사용
- **P7** [3] [CLS] | 분류 작업을 위한 집계 시퀀스 표현으로 사용하는 특수 토큰
- **P8** [3] [SEP] | 문장 쌍을 구분하는 특수 구분 토큰
