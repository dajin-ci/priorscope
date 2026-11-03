# S3 라벨 시트

- 내 논문: End-to-End Object Detection with Transformers
- 기존 논문: Conformer: Convolution-augmented Transformer for Speech Recognition

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

- Modern detectors address this set prediction task in an indirect way, by defining surrogate regression and classification problems on a large set of proposals, anchors, or window centers.
- Their performances are significantly influenced by postprocessing steps to collapse near-duplicate predictions, by the design of the anchor sets and by the heuristics that assign target boxes to anchors.
- previous attempts either add other forms of prior knowledge, or have not proven to be competitive with strong baselines on challenging benchmarks.
- It obtains, however, lower performances on small objects.
- This new design for detectors also comes with new challenges, in particular regarding training, optimization and performances on small objects.

## 내 논문 contributions

- [1] We present a new method that views object detection as a direct set prediction problem.
- [1] The main ingredients of the new framework, called DEtection TRansformer or DETR, are a set-based global loss that forces unique predictions via bipartite matching, and a transformer encoder-decoder architecture.
- [1] Given a fixed small set of learned object queries, DETR reasons about the relations of the objects and the global image context to directly output the final set of predictions in parallel.
- [1] The new model is conceptually simple and does not require a specialized library, unlike many other modern detectors.
- [1] DETR demonstrates accuracy and run-time performance on par with the well-established and highly-optimized Faster R-CNN baseline on the challenging COCO object detection dataset.
- [1] DETR can be easily generalized to produce panoptic segmentation in a unified manner.
- [1] We show that it significantly outperforms competitive baselines.

## 내 논문 experiment_results

- COCO | Faster RCNN-DC5 | dev | single | 없음 | AP | 39.0 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5 | dev | single | 없음 | AP50 | 60.5 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5 | dev | single | 없음 | AP75 | 42.3 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5 | dev | single | 없음 | APs | 21.4 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5 | dev | single | 없음 | APM | 43.5 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5 | dev | single | 없음 | APL | 52.5 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN | dev | single | 없음 | AP | 40.2 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN | dev | single | 없음 | AP50 | 61.0 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN | dev | single | 없음 | AP75 | 43.8 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN | dev | single | 없음 | APs | 24.2 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN | dev | single | 없음 | APM | 43.5 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN | dev | single | 없음 | APL | 52.0 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN | dev | single | 없음 | AP | 42.0 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN | dev | single | 없음 | AP50 | 62.5 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN | dev | single | 없음 | AP75 | 45.9 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN | dev | single | 없음 | APs | 25.2 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN | dev | single | 없음 | APM | 45.6 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN | dev | single | 없음 | APL | 54.6 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5+ | dev | single | 없음 | AP | 41.1 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5+ | dev | single | 없음 | AP50 | 61.4 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5+ | dev | single | 없음 | AP75 | 44.3 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5+ | dev | single | 없음 | APs | 22.9 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5+ | dev | single | 없음 | APM | 45.9 | ↑ | [Table 1]
- COCO | Faster RCNN-DC5+ | dev | single | 없음 | APL | 55.0 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN+ | dev | single | 없음 | AP | 42.0 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN+ | dev | single | 없음 | AP50 | 62.1 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN+ | dev | single | 없음 | AP75 | 45.5 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN+ | dev | single | 없음 | APs | 26.6 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN+ | dev | single | 없음 | APM | 45.4 | ↑ | [Table 1]
- COCO | Faster RCNN-FPN+ | dev | single | 없음 | APL | 53.4 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN+ | dev | single | 없음 | AP | 44.0 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN+ | dev | single | 없음 | AP50 | 63.9 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN+ | dev | single | 없음 | AP75 | 47.8 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN+ | dev | single | 없음 | APs | 27.2 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN+ | dev | single | 없음 | APM | 48.1 | ↑ | [Table 1]
- COCO | Faster RCNN-R101-FPN+ | dev | single | 없음 | APL | 56.0 | ↑ | [Table 1]
- COCO | DETR | dev | single | 없음 | AP | 42.0 | ↑ | [Table 1]
- COCO | DETR | dev | single | 없음 | AP50 | 62.4 | ↑ | [Table 1]
- COCO | DETR | dev | single | 없음 | AP75 | 44.2 | ↑ | [Table 1]
- COCO | DETR | dev | single | 없음 | APs | 20.5 | ↑ | [Table 1]
- COCO | DETR | dev | single | 없음 | APM | 45.8 | ↑ | [Table 1]
- COCO | DETR | dev | single | 없음 | APL | 61.1 | ↑ | [Table 1]
- COCO | DETR-DC5 | dev | single | 없음 | AP | 43.3 | ↑ | [Table 1]
- COCO | DETR-DC5 | dev | single | 없음 | AP50 | 63.1 | ↑ | [Table 1]
- COCO | DETR-DC5 | dev | single | 없음 | AP75 | 45.9 | ↑ | [Table 1]
- COCO | DETR-DC5 | dev | single | 없음 | APs | 22.5 | ↑ | [Table 1]
- COCO | DETR-DC5 | dev | single | 없음 | APM | 47.3 | ↑ | [Table 1]
- COCO | DETR-DC5 | dev | single | 없음 | APL | 61.1 | ↑ | [Table 1]
- COCO | DETR-R101 | dev | single | 없음 | AP | 43.5 | ↑ | [Table 1]
- COCO | DETR-R101 | dev | single | 없음 | AP50 | 63.8 | ↑ | [Table 1]
- COCO | DETR-R101 | dev | single | 없음 | AP75 | 46.4 | ↑ | [Table 1]
- COCO | DETR-R101 | dev | single | 없음 | APs | 21.9 | ↑ | [Table 1]
- COCO | DETR-R101 | dev | single | 없음 | APM | 48.0 | ↑ | [Table 1]
- COCO | DETR-R101 | dev | single | 없음 | APL | 61.8 | ↑ | [Table 1]
- COCO | DETR-DC5-R101 | dev | single | 없음 | AP | 44.9 | ↑ | [Table 1]
- COCO | DETR-DC5-R101 | dev | single | 없음 | AP50 | 64.7 | ↑ | [Table 1]
- COCO | DETR-DC5-R101 | dev | single | 없음 | AP75 | 47.7 | ↑ | [Table 1]
- COCO | DETR-DC5-R101 | dev | single | 없음 | APs | 23.7 | ↑ | [Table 1]
- COCO | DETR-DC5-R101 | dev | single | 없음 | APM | 49.5 | ↑ | [Table 1]
- COCO | DETR-DC5-R101 | dev | single | 없음 | APL | 62.3 | ↑ | [Table 1]
- COCO | PanopticFPN++ | dev | single | 없음 | PQ | 42.4 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | SQ | 79.3 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | RQ | 51.6 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | PQth | 49.2 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | SQth | 82.4 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | RQth | 58.8 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | PQst | 32.3 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | SQst | 74.8 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | RQ⁵t | 40.6 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | AP | 37.7 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | PQ | 42.5 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | SQ | 78.0 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | RQ | 52.5 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | PQth | 48.6 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | SQth | 79.4 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | RQth | 59.6 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | PQst | 33.4 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | SQst | 75.9 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | RQ⁵t | 41.7 | ↑ | [Table 5]
- COCO | UPSnet | dev | single | 없음 | AP | 34.3 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | PQ | 43.0 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | SQ | 79.1 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | RQ | 52.8 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | PQth | 48.9 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | SQth | 79.7 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | RQth | 59.7 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | PQst | 34.1 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | SQst | 78.2 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | RQ⁵t | 42.3 | ↑ | [Table 5]
- COCO | UPSnet-M | dev | single | 없음 | AP | 34.3 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | PQ | 44.1 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | SQ | 79.5 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | RQ | 53.3 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | PQth | 51.0 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | SQth | 83.2 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | RQth | 60.6 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | PQst | 33.6 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | SQst | 74.0 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | RQ⁵t | 42.1 | ↑ | [Table 5]
- COCO | PanopticFPN++ | dev | single | 없음 | AP | 39.7 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | PQ | 43.4 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | SQ | 79.3 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | RQ | 53.8 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | PQth | 48.2 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | SQth | 79.8 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | RQth | 59.5 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | PQst | 36.3 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | SQst | 78.5 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | RQ⁵t | 45.3 | ↑ | [Table 5]
- COCO | DETR | dev | single | 없음 | AP | 31.1 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | PQ | 44.6 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | SQ | 79.8 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | RQ | 55.0 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | PQth | 49.4 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | SQth | 80.5 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | RQth | 60.6 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | PQst | 37.3 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | SQst | 78.7 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | RQ⁵t | 46.5 | ↑ | [Table 5]
- COCO | DETR-DC5 | dev | single | 없음 | AP | 31.9 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | PQ | 45.1 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | SQ | 79.9 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | RQ | 55.5 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | PQth | 50.5 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | SQth | 80.9 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | RQth | 61.7 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | PQst | 37.0 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | SQst | 78.5 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | RQ⁵t | 46.0 | ↑ | [Table 5]
- COCO | DETR-R101 | dev | single | 없음 | AP | 33.0 | ↑ | [Table 5]

## 기존 논문 problem

- Transformer models are good at capturing content-based global interactions, while CNNs exploit local features effectively.
- However, models with self-attention or convolutions each has its limitations.
- While Transformers are good at modeling long-range global context, they are less capable to extract fine-grained local feature patterns.
- One limitation of using local connectivity is that you need many more layers or parameters to capture global information.
- However, it is still limited in capturing dynamic global context as it only applies a global averaging over the entire sequence.

## 기존 논문 contributions

- [1] we propose the convolution-augmented transformer for speech recognition, named Conformer. [1] Conformer significantly outperforms the previous Transformer and CNN based models achieving state-of-the-art accuracies. [1] On the widely used LibriSpeech benchmark, our model achieves WER of 2.1%/4.3% without using a language model and 1.9%/3.9% with an external language model on test/testother. [1] We also observe competitive performance of 2.7%/6.3% with a small model of only 10M parameters. [1] We further carefully study the effects of the number of attention heads, convolution kernel sizes, activation functions, placement of feed-forward layers, and different strategies of adding convolution modules to a Transformer-based network, and shed light on how each contributes to the accuracy improvements.

## 기존 논문 limitations

- (추출되지 않음)

## 기존 논문 experiment_results

- LibriSpeech | Conformer(S) | test | single | 없음 | WER | 2.7 | ↓ | [Table 2]
- LibriSpeech | Conformer(S) | test | single | 없음 | WER | 6.3 | ↓ | [Table 2]
- LibriSpeech | Conformer(S) | test | single | LM | WER | 2.1 | ↓ | [Table 2]
- LibriSpeech | Conformer(S) | test | single | LM | WER | 5.0 | ↓ | [Table 2]
- LibriSpeech | Conformer(M) | test | single | 없음 | WER | 2.3 | ↓ | [Table 2]
- LibriSpeech | Conformer(M) | test | single | 없음 | WER | 5.0 | ↓ | [Table 2]
- LibriSpeech | Conformer(M) | test | single | LM | WER | 2.0 | ↓ | [Table 2]
- LibriSpeech | Conformer(M) | test | single | LM | WER | 4.3 | ↓ | [Table 2]
- LibriSpeech | Conformer(L) | test | single | 없음 | WER | 2.1 | ↓ | [Table 2]
- LibriSpeech | Conformer(L) | test | single | 없음 | WER | 4.3 | ↓ | [Table 2]
- LibriSpeech | Conformer(L) | test | single | LM | WER | 1.9 | ↓ | [Table 2]
- LibriSpeech | Conformer(L) | test | single | LM | WER | 3.9 | ↓ | [Table 2]

## 내 논문 요소 (M)

- **M1** [1] direct set prediction problem | 객체 검출을 직접 집합 예측 문제로 정식화하는 접근
- **M2** [1] a set-based global loss that forces unique predictions via bipartite matching | 이분 매칭을 통해 중복 없는 유일한 예측을 강제하는 집합 기반 전역 손실
- **M3** [1] a transformer encoder-decoder architecture | 트랜스포머 인코더-디코더 구조
- **M4** [1] a fixed small set of learned object queries | 학습된 소수의 객체 쿼리 집합을 사용해 객체를 병렬 예측
- **M5** [2.1] bipartite matching loss | 정답 객체와 예측 객체 간 일대일 할당을 위한 이분 매칭 손실
- **M6** [2.2] parallel decoding | 비자기회귀적 병렬 디코딩
- **M7** [3.1] Hungarian algorithm | 최적 이분 매칭 계산을 위한 헝가리안 알고리즘
- **M8** [3.1] a linear combination of the l₁ loss and the generalized IoU loss | 박스 회귀를 위해 l1 손실과 GIoU 손실을 결합
- **M9** [3.2] a CNN backbone | 이미지 특징 추출을 위한 CNN 백본
- **M10** [3.2] Prediction feed-forward networks (FFNs) | 디코더 출력으로부터 클래스와 박스를 예측하는 FFN 헤드
- **M11** [3.2] auxiliary losses | 각 디코더 층 뒤에 추가 손실을 두어 학습을 돕는 보조 디코딩 손실

## 기존 논문 요소 (P)

- **P1** [2.1] multi-headed self-attention (MHSA) | 다중 헤드 자기어텐션 모듈을 사용한다.
- **P2** [2.1] relative sinusoidal positional encoding scheme | 상대적 사인파 위치 인코딩을 사용해 길이 일반화와 강건성을 높인다.
- **P3** [2.1] pre-norm residual units | 잔차 유닛 내부에 사전 정규화를 적용한다.
- **P4** [2.2] a pointwise convolution and a gated linear unit (GLU) | 포인트와이즈 합성곱과 GLU 게이팅으로 시작하는 합성곱 모듈이다.
- **P5** [2.2] single 1-D depthwise convolution layer | 지역 문맥 포착을 위한 1차원 depthwise convolution을 사용한다.
- **P6** [2.2] Batchnorm | 깊은 모델 학습을 돕기 위해 합성곱 뒤에 배치정규화를 둔다.
- **P7** [2.3] Swish activation | 피드포워드 모듈에서 Swish 활성화를 사용한다.
- **P8** [2.4] two Feed Forward modules sandwiching the Multi-Headed Self-Attention module and the Convolution module | 어텐션과 합성곱 모듈을 두 개의 FFN이 감싸는 샌드위치 구조를 사용한다.
- **P9** [2.4] Macaron-Net | Macaron-Net에서 영감을 받은 이중 FFN 구조를 사용한다.
- **P10** [2.4] half-step residual weights | FFN 모듈에 half-step residual을 적용한다.
- **P11** [3.1] SpecAugment | 입력 음성 특징에 데이터 증강을 적용한다.
- **P12** [3.2] shallow fusion | 외부 언어모델과의 얕은 결합으로 성능을 높인다.
