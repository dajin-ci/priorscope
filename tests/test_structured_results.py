"""9열 구조 형식 실험 결과의 조건 비교 테스트 (Studio 호출 없음)."""

import validator as v


def _paper(results):
    return {"core_techniques": ["[1] a | b"], "experiment_results": results}


def _run(my_rows, prior_rows, pairs):
    compare = {"element_mapping": ["M1 ↔ - | 없음 | 검토 범위 P1 | e"], "result_pairs": pairs}
    out = v.validate(_paper(my_rows), _paper(prior_rows), compare)
    return {(c["my_result_id"], c["prior_result_id"]): c for c in out["numeric_checks"]}


MY = [
    "SQuAD 2.0 | RoBERTa | dev | single | w/o data augmentation | F1 | 89.4 | ↑ | [Table 6]",
    "SQuAD 2.0 | RoBERTa | test | single | 없음 | F1 | 89.8 | ↑ | [Table 6]",
    "MNLI-m | RoBERTa | test | ensemble | 없음 | Acc. | 90.8 | ↑ | [Table 5]",
    "SQuAD 1.1 | RoBERTa | dev | single | 없음 | F1 | 94.6 | ↑ | [Table 6]",
]
PRIOR = [
    "SQuAD v2.0 | BERTLARGE | dev | single | 없음 | F1 | 81.9 | ↑ | [Table 3]",
    "SQuAD v2.0 | BERTLARGE | test | single | 없음 | F1 | 83.1 | ↑ | [Table 3]",
    "MNLI-m | BERTLARGE | test | single | 없음 | Acc. | 86.7 | ↑ | [Table 1]",
    "SQuAD v1.1 | BERTLARGE | dev | single | TriviaQA | F1 | 91.1 | ↑ | [Table 2]",
]


def test_code_decides_conditions_even_if_agent_disagrees():
    checks = _run(MY, PRIOR, ["R-M1 ~ R-P1 | 조건 다름 | 표기가 다름"])
    c = checks[("R-M1", "R-P1")]
    assert c["outcome"] == "우세" and c["condition_judge"] == "code"
    assert any("Compare Agent는 조건 다름" in w for w in c["warnings"])


def test_code_adds_missed_comparable_pair():
    checks = _run(MY, PRIOR, [])
    assert checks[("R-M2", "R-P2")]["outcome"] == "우세"
    assert checks[("R-M2", "R-P2")].get("added_by_code")
    # 조건이 다른 쌍(dev vs test)은 추가하지 않는다
    assert ("R-M1", "R-P2") not in checks


def test_ensemble_vs_single_is_incomparable():
    checks = _run(MY, PRIOR, ["R-M3 ~ R-P3 | 동일 조건 | x"])
    c = checks[("R-M3", "R-P3")]
    assert c["outcome"] == "비교 불가" and "모델 구성" in c["reason"]


def test_extra_data_difference_is_incomparable():
    checks = _run(MY, PRIOR, ["R-M4 ~ R-P4 | 동일 조건 | x"])
    assert "추가 데이터" in checks[("R-M4", "R-P4")]["reason"]


def test_unknown_split_is_incomparable():
    my = ["SQuAD 2.0 | RoBERTa | ? | single | 없음 | F1 | 89.4 | ↑ | [Table 6]"]
    checks = _run(my, PRIOR[:1], ["R-M1 ~ R-P1 | 동일 조건 | x"])
    assert "확인할 수 없습니다" in checks[("R-M1", "R-P1")]["reason"]


def test_empty_extra_is_not_none():
    my = ["SQuAD 2.0 | RoBERTa | dev | single |  | F1 | 89.4 | ↑ | [Table 6]"]
    checks = _run(my, PRIOR[:1], ["R-M1 ~ R-P1 | 동일 조건 | x"])
    assert checks[("R-M1", "R-P1")]["outcome"] == "비교 불가"


def test_legacy_six_column_still_uses_agent_label():
    my = ["SQuAD 2.0 | RoBERTa, dev | F1 | 89.4 | ↑ | [Table 6]"]
    prior = ["SQuAD v2.0 | BERT, dev | F1 | 81.9 | ↑ | [Table 3]"]
    assert _run(my, prior, ["R-M1 ~ R-P1 | 조건 다름 | x"])[("R-M1", "R-P1")]["outcome"] == "비교 불가"
    assert _run(my, prior, ["R-M1 ~ R-P1 | 동일 조건 | x"])[("R-M1", "R-P1")]["outcome"] == "우세"


def test_unknown_metric_is_never_paired():
    # 양쪽 지표가 모두 '?'여도 같은 지표로 짝짓지 않는다.
    my = ["SQuAD 2.0 | RoBERTa | test | single | 없음 | ? | 89.8 | ↑ | [Table 6]"]
    prior = ["SQuAD v2.0 | BERT | test | single | 없음 | ? | 83.1 | ↑ | [Table 3]"]
    compare = {"element_mapping": ["M1 ↔ - | 없음 | 검토 범위 P1 | e"], "result_pairs": []}
    out = v.validate(_paper(my), _paper(prior), compare)
    assert out["expected_result_pairs"] == [] and out["numeric_checks"] == []


def test_unknown_metric_reason():
    my = ["SQuAD 2.0 | RoBERTa | test | single | 없음 | ? | 89.8 | ↑ | [Table 6]"]
    checks = _run(my, PRIOR[1:2], ["R-M1 ~ R-P1 | 동일 조건 | x"])
    assert checks[("R-M1", "R-P1")]["reason"] == "지표를 확인할 수 없습니다."
