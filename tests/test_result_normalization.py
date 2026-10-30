"""정량 비교 표기 정규화 테스트 (Studio 호출 없음)."""

import validator as v


def test_dataset_version_v_is_ignored():
    assert v._canon_dataset("SQuAD 2.0") == v._canon_dataset("SQuAD v2.0")
    assert v._canon_dataset("SQuAD V1.1") == v._canon_dataset("squad 1.1")


def test_dataset_name_with_v_is_kept():
    # ImageNetV2는 ImageNet과 다른 데이터셋이다.
    assert v._canon_dataset("ImageNetV2") != v._canon_dataset("ImageNet")


def test_different_versions_stay_different():
    assert v._canon_dataset("SQuAD v1.1") != v._canon_dataset("SQuAD v2.0")


def test_roberta_bert_pairs_are_compared():
    my = {"core_techniques": ["[1] a | b"],
          "experiment_results": ["GLUE | RoBERTa | Avg. | 88.5 | ↑ | [Table 5]",
                                 "SQuAD 2.0 | RoBERTa | F1 | 89.4 | ↑ | [Table 6]"]}
    prior = {"core_techniques": ["[3] c | d"],
             "experiment_results": ["GLUE | BERTLARGE | Avg. | 82.1 | ↑ | [Table 1]",
                                    "SQuAD v2.0 | BERTLARGE (Single) | F1 | 83.1 | ↑ | [Table 3]"]}
    compare = {"element_mapping": ["M1 ↔ - | 없음 | 검토 범위 P1 | e"],
               "result_pairs": ["R-M1 ~ R-P1 | 동일 조건 | x", "R-M2 ~ R-P2 | 동일 조건 | y"]}
    out = v.validate(my, prior, compare)
    assert out["expected_result_pairs"] == [["R-M1", "R-P1"], ["R-M2", "R-P2"]]
    assert [c["outcome"] for c in out["numeric_checks"]] == ["우세", "우세"]
