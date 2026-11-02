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
