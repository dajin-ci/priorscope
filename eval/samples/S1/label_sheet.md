# S1 라벨 시트

- 내 논문: Towards Open-Vocabulary Audio-Visual Event Localization
- 기존 논문: IMAGEBIND: One Embedding Space To Bind Them All

## 라벨 기준

- 일치: 기존 논문에 같은 기법이 있다 (용어·언어가 달라도 같은 것)
- 유사: 기존 논문의 핵심 아이디어를 가져다 쓰거나 변형했다
- 없음: 기존 논문에 없다. Transformer 사용, 손실 함수 학습처럼 흔한 기법만 같으면 없음
- 확인필요: 논문을 다시 봐도 판단이 어렵다

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

- 기존 AVEL 연구는 closed-set 가정에 머물러 학습 중 보지 못한(unseen) 이벤트 카테고리가 포함된 테스트 데이터를 처리하기 어렵다.
- 기존 open-set AVEL은 unseen 이벤트를 "unknown"으로만 인식할 수 있어 카테고리별 의미를 제공하지 못한다.

## 내 논문 contributions

- [1] We propose the Open-Vocabulary Audio-Visual Event Localization (OV-AVEL) task, aiming to localize both seen and unseen audio-visual events in test videos.
- [1] To facilitate this new task, we construct the OV-AVEBench dataset, which includes segment-level manual event annotations.
- [1] Besides, we establish standard evaluation metrics that encompass typical accuracy, as well as segment-level and event-level Fl-scores.
- [1] We present two simple baselines: one adopting a training-free paradigm, which can be upgraded through further fine-tuning on available training data.

## 내 논문 experiment_results

- OV-AVEBench | Training-free (our), total | Avg. | 46.6 | ↑ | [Table 2]
- OV-AVEBench | Training-free (our), seen | Avg. | 45.5 | ↑ | [Table 2]
- OV-AVEBench | Training-free (our), unseen | Avg. | 47.0 | ↑ | [Table 2]
- OV-AVEBench | Fine-tuning (our), total | Avg. | 57.8 | ↑ | [Table 2]
- OV-AVEBench | Fine-tuning (our), seen | Avg. | 62.9 | ↑ | [Table 2]
- OV-AVEBench | Fine-tuning (our), unseen | Avg. | 55.8 | ↑ | [Table 2]

## 기존 논문 problem

- Existing methods typically learn embeddings for only a single pair or a few visual modalities, so the final embeddings are limited to the pairs of modalities used for training.
- Learning a true joint embedding is hindered by the absence of large quantities of multimodal data where all modalities are present together.
- Acquiring all types and combinations of paired data with the same set of images is infeasible.

## 기존 논문 contributions

- [1] We present IMAGEBIND, which learns a single shared representation space by leveraging multiple types of image-paired data. It does not need datasets where all modalities co-occur with each other. Instead, we leverage the binding property of images and we show that just aligning each modality's embedding to image embeddings leads to an emergent alignment across all of the modalities. IMAGEBIND can be initialized with large-scale vision-language models such as CLIP [60], thereby leveraging the rich image and text representations of these models. We use large-scale image-text paired data along with naturally paired 'self-supervised' data across four new modalities - audio, depth, thermal, and Inertial Measurement Unit (IMU) readings - and show strong emergent zero-shot classification and retrieval performance on tasks for each of these modalities. Finally, we show that IMAGEBIND's joint embeddings can be used for a wide variety of compositional tasks, including cross-modal retrieval, combining embeddings via arithmetic, detecting audio sources in images, and generating images given audio input.

## 기존 논문 limitations

- [6] Our embeddings are trained without a specific downstream task, and thus lag the performance of specialist models.
- [6] Our model is a research prototype and cannot be readily used for real world applications ( Appendix F).
- [F] joint embedding models, including IMAGEBIND must be studied carefully with a lens towards measuring such associations, and their implications.
- [F] IMAGEBIND leverages the image-text embeddings learned by a pretrained model on large web-based data which has biases as documented in different studies [60].
- [F] These joint embeddings are thus limited to the concepts present in the datasets.
- [F] the thermal datasets we used are limited to outdoor street scenes, while the depth datasets are limited to indoor scenes.

## 기존 논문 experiment_results

- IN1K | IMAGEBIND | Acc. | 77.7 | ↑ | [Table 2]
- P365 | IMAGEBIND | Acc. | 45.4 | ↑ | [Table 2]
- K400 | IMAGEBIND | Acc. | 50.0 | ↑ | [Table 2]
- MSR-VTT | IMAGEBIND | Recall@1 | 36.1 | ↑ | [Table 2]
- NYU-D | IMAGEBIND | Acc. | 54.0 | ↑ | [Table 2]
- SUN-D | IMAGEBIND | Acc. | 35.1 | ↑ | [Table 2]
- AS-A | IMAGEBIND | mAP | 17.6 | ↑ | [Table 2]
- VGGS | IMAGEBIND | Acc. | 27.8 | ↑ | [Table 2]
- ESC | IMAGEBIND | Acc. | 66.9 | ↑ | [Table 2]
- LLVIP | IMAGEBIND | Acc. | 63.4 | ↑ | [Table 2]
- Ego4D | IMAGEBIND | Acc. | 25.0 | ↑ | [Table 2]
- Clotho | IMAGEBIND | R@1 | 6.0 | ↑ | [Table 3]
- Clotho | IMAGEBIND | R@10 | 28.4 | ↑ | [Table 3]
- AudioCaps | IMAGEBIND | R@1 | 9.3 | ↑ | [Table 3]
- AudioCaps | IMAGEBIND | R@10 | 42.3 | ↑ | [Table 3]
- ESC | IMAGEBIND | Top-1 | 66.9 | ↑ | [Table 3]
- MSR-VTT 1K-A | IMAGEBIND, A | R@1 | 6.8 | ↑ | [Table 4]
- MSR-VTT 1K-A | IMAGEBIND, A | R@5 | 18.5 | ↑ | [Table 4]
- MSR-VTT 1K-A | IMAGEBIND, A | R@10 | 27.2 | ↑ | [Table 4]
- MSR-VTT 1K-A | IMAGEBIND, A+V | R@1 | 36.8 | ↑ | [Table 4]
- MSR-VTT 1K-A | IMAGEBIND, A+V | R@5 | 61.8 | ↑ | [Table 4]
- MSR-VTT 1K-A | IMAGEBIND, A+V | R@10 | 70.0 | ↑ | [Table 4]

## 내 논문 요소 (M)

- **M1** [1] the Open-Vocabulary Audio-Visual Event Localization (OV-AVEL) problem | seen과 unseen 테스트 데이터 모두에 대해 명시적 이벤트 카테고리를 예측하는 개방어휘 AVEL 문제를 정식화
- **M2** [1] the OV-AVEBench dataset | 67개 실생활 오디오-비주얼 장면과 수동 segment-level 주석을 포함한 데이터셋 구축
- **M3** [1] three evaluation metrics | 정확도와 segment-level/event-level F1을 포함한 평가 지표를 정립
- **M4** [1] the unified multimodal space from the pretrained ImageBind model | 사전학습된 ImageBind의 통합 멀티모달 임베딩 공간에서 오디오·비주얼·텍스트 특징을 추출
- **M5** [1] comparing the consistency of audio-text and visual-text feature similarities | 오디오-텍스트와 비주얼-텍스트 유사도의 일치성으로 예측하는 학습 없는 베이스라인
- **M6** [1] lightweight temporal layers to encode temporal relations within the audio and visual modalities | 오디오/비주얼 모달리티 내부의 시간 관계를 학습하기 위한 경량 temporal layer 삽입
- **M7** [3.2] a stack of L standard Transformer [41] blocks | temporal layer를 표준 Transformer 블록 스택으로 구현해 시간 상호작용을 강화
- **M8** [3.2] The ground truth Y' E RT×(C¹ for the training data can be easily obtained by select- ing columns of corresponding seen classes from Y E RT×(C+1). Then, our fine-tuning baseline is trained by op- timizing the cross entropy loss between Save and Y'. | seen 클래스 열만 사용한 정답과 Save 사이의 cross entropy로 미세조정 학습

## 기존 논문 요소 (P)

- **P1** [3.2] aligning each modality's embedding to image embeddings leads to an emergent alignment across all of the modalities | 각 모달리티 임베딩을 이미지 임베딩에 정렬해 보지 않은 모달리티 쌍 사이의 정렬이 자연스럽게 발생하도록 함
- **P2** [3.2] We use large-scale web datasets with (image, text) pairings | 대규모 웹 기반 이미지-텍스트 페어 데이터를 활용함
- **P3** [3.2] we use the natural, self-supervised pairing of other modalities - audio, depth, thermal, and In- tertial Measurement Unit (IMU) - with images | 오디오·깊이·열·IMU와 이미지의 자연적 자기지도 페어링을 사용함
- **P4** [3.2] are optimized using an InfoNCE [54] loss | 모달리티-이미지 정렬을 위해 InfoNCE 대조학습 손실을 사용함
- **P5** [3.2] we use a symmetric loss LI,M + LM,I | 양방향 대칭 손실로 두 모달리티 정렬을 학습함
- **P6** [3.3] We use a Transformer architecture [73] for all the modality encoders | 모든 모달리티 인코더에 Transformer 아키텍처를 사용함
- **P7** [3.3] We use separate encoders for images, text, audio, ther- mal images, depth images, and IMU | 모달리티별로 분리된 인코더를 사용함
- **P8** [3.3] We add a modality- specific linear projection head on each encoder to obtain a fixed size d dimensional embedding | 각 인코더 뒤에 모달리티별 선형 프로젝션 헤드를 붙여 고정 차원 임베딩을 생성함
