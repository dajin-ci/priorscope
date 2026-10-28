"""규칙 기반 PriorScope 비교 결과 검증기.

구성
- validate_comparison(): Compare Agent 결과의 형식·번호·근거를 검사해 보고서를 만든다.
- validate(): app.py / service.py가 부르는 진입점. 세 JSON을 받아
  원본 목록을 만들고, 강등된 대응표·커버리지 범위·최종 등급까지 계산한다.

원칙: Compare Agent 결과는 수정하지 않는다. 화면용 판정은 별도로 만들며,
근거에 문제가 있으면 "확인필요"로 강등만 하고 승격하지 않는다.
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


_SINGLE_FIELDS = ("overlap_level", "llm_score", "summary", "related_work_draft")
_LIST_FIELDS = (
    "element_mapping",
    "result_pairs",
    "caution_points",
    "differentiation_suggestions",
)
_VERDICTS = {"일치", "유사", "없음", "확인필요"}
_OVERLAP_LEVELS = {"High Overlap", "Medium Overlap", "Low Overlap"}
_ID_PATTERNS = {
    "M": re.compile(r"^M\d+$"),
    "P": re.compile(r"^P\d+$"),
    "R-M": re.compile(r"^R-M\d+$"),
    "R-P": re.compile(r"^R-P\d+$"),
}
_NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _issue(
    report: dict[str, Any],
    code: str,
    severity: str,
    path: str,
    message: str,
    *,
    item_id: str | None = None,
    expected: Any = None,
    actual: Any = None,
) -> None:
    entry: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "path": path,
        "item_id": item_id,
        "message": message,
    }
    if expected is not None:
        entry["expected"] = expected
    if actual is not None:
        entry["actual"] = actual
    report["issues"].append(entry)


def _not_checked(report: dict[str, Any], code: str, path: str, reason: str) -> None:
    item = {"code": code, "path": path, "reason": reason}
    if item not in report["not_checked"]:
        report["not_checked"].append(item)


def _coverage(expected: list[Any] | None, observed: list[Any]) -> dict[str, Any]:
    # 예상 목록이 없으면 관측된 개수만 보고하고 커버리지 비율은 단정하지 않는다.
    if expected is None:
        return {
            "expected_count": None,
            "observed_count": len(observed),
            "processed_count": None,
            "missing": [],
            "duplicates": [],
            "out_of_scope": [],
            "ratio": None,
        }
    counts = Counter(observed)
    expected_set = set(expected)
    observed_set = set(observed)
    processed = len(expected_set & observed_set)
    # 예상 항목이 0개인 경우 0으로 나누지 않으며 비율도 정의하지 않는다.
    ratio = processed / len(expected_set) if expected_set else None
    return {
        "expected_count": len(expected),
        "observed_count": len(observed),
        "processed_count": processed,
        "missing": sorted(expected_set - observed_set),
        "duplicates": sorted(item for item, count in counts.items() if count > 1),
        "out_of_scope": sorted(observed_set - expected_set),
        "ratio": ratio,
    }


def _parse_mapping(line: str) -> dict[str, Any] | None:
    # 정해진 4개 열 형식만 허용한다. 잘못된 형식을 추측해 고치면 누락이 가려질 수 있다.
    parts = [part.strip() for part in line.split("|")]
    if len(parts) != 4:
        return None
    head = re.fullmatch(r"(M\d+)\s*↔\s*(.+)", parts[0])
    if not head:
        return None
    item_id, prior_text = head.groups()
    prior_text = prior_text.strip()
    prior_ids: list[str] = []
    if prior_text != "-":
        refs = [ref.strip() for ref in prior_text.split(",")]
        if not refs or any(not re.fullmatch(r"P\d+", ref) for ref in refs):
            return None
        prior_ids = refs
    return {
        "item_id": item_id,
        "prior_ids": prior_ids,
        "verdict": parts[1],
        "evidence": parts[2],
        "explanation": parts[3],
    }


def _parse_result_pair(line: str) -> tuple[str, str] | None:
    # 검증에는 두 결과 ID만 사용한다.
    # 규격: "R-M1 ~ R-P2 | 동일 조건 또는 조건 다름 | 설명" (3열). 설명만 있는 2열도 허용한다.
    parts = [part.strip() for part in line.split("|")]
    if len(parts) not in (2, 3):
        return None
    match = re.fullmatch(r"(R-M\d+)\s*~\s*(R-P\d+)", parts[0])
    return match.groups() if match else None


def _parse_number(value: Any) -> float | None:
    # Python에서 bool은 int의 하위 타입이므로 숫자로 잘못 받아들이지 않게 먼저 제외한다.
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            number = float(value)
        except (OverflowError, ValueError):
            return None
        # NaN/무한대는 JSON 결과나 차이 계산을 깨뜨릴 수 있어 유한값만 통과시킨다.
        return number if math.isfinite(number) else None
    if isinstance(value, str) and _NUMBER_PATTERN.fullmatch(value.strip()):
        try:
            number = float(value.strip())
        except (OverflowError, ValueError):
            return None
        return number if math.isfinite(number) else None
    return None


def _record_index(
    source_records: Mapping[str, Any] | None,
    key: str,
    report: dict[str, Any],
) -> dict[str, Mapping[str, Any]] | None:
    # 원본 목록별로 색인을 만든다. M1과 P1은 서로 다른 목록의 ID라 공존할 수 있다.
    if source_records is None:
        return None
    if key not in source_records:
        _issue(
            report,
            "SOURCE_RECORDS_MISSING",
            "review",
            f"source_records.{key}",
            "원본 레코드 목록이 전달되지 않아 해당 참조 검사를 완료할 수 없습니다.",
        )
        _not_checked(
            report,
            "SOURCE_RECORDS_MISSING",
            f"source_records.{key}",
            "원본 레코드 목록이 전달되지 않아 참조 검사를 수행할 수 없습니다.",
        )
        return None
    records = source_records[key]
    if not _is_sequence(records):
        _issue(
            report,
            "FIELD_TYPE_INVALID",
            "error",
            f"source_records.{key}",
            "원본 레코드 목록은 배열이어야 합니다.",
            expected="array",
            actual=type(records).__name__,
        )
        return None
    if key in ("M", "P") and not records:
        _issue(
            report,
            "SOURCE_LIST_EMPTY",
            "error",
            f"source_records.{key}",
            "MVP 규격에서 논문별 핵심 기술 요소 목록은 비어 있을 수 없습니다.",
        )
    index: dict[str, Mapping[str, Any]] = {}
    for position, record in enumerate(records):
        path = f"source_records.{key}[{position}]"
        if not isinstance(record, Mapping):
            _issue(
                report,
                "FIELD_TYPE_INVALID",
                "error",
                path,
                "원본 레코드는 객체여야 합니다.",
                expected="object",
                actual=type(record).__name__,
            )
            continue
        identifier = record.get("id")
        if not isinstance(identifier, str) or not _ID_PATTERNS[key].fullmatch(identifier):
            _issue(
                report,
                "IDENTIFIER_FORMAT_INVALID",
                "error",
                f"{path}.id",
                "원본 식별번호 형식이 MVP의 M/P/R 규칙과 맞지 않습니다.",
                expected=key + "<숫자>",
                actual=identifier if isinstance(identifier, (str, int, float)) else type(identifier).__name__,
            )
            continue
        if identifier in index:
            _issue(
                report,
                "SOURCE_ID_DUPLICATE",
                "error",
                f"{path}.id",
                "같은 원본 목록 안에 식별번호가 중복되어 있습니다.",
                item_id=identifier,
            )
            continue
        index[identifier] = record
    return index


def _validate_schema(comparison_result: Any, report: dict[str, Any]) -> None:
    # Compare Agent 출력은 단일 값도 배열로 감싼다는 MVP 규격을 검사한다.
    if not isinstance(comparison_result, Mapping):
        _issue(
            report,
            "INPUT_TYPE_INVALID",
            "error",
            "comparison_result",
            "비교 결과는 객체여야 합니다.",
            expected="object",
            actual=type(comparison_result).__name__,
        )
        return

    for field in (*_SINGLE_FIELDS, *_LIST_FIELDS):
        path = f"comparison_result.{field}"
        if field not in comparison_result:
            _issue(
                report,
                "REQUIRED_FIELD_MISSING",
                "error",
                path,
                "MVP 비교 결과에 필요한 필드가 없습니다.",
            )
            continue
        value = comparison_result[field]
        if not _is_sequence(value):
            _issue(
                report,
                "FIELD_TYPE_INVALID",
                "error",
                path,
                "MVP Compare Agent 규격의 필드는 배열이어야 합니다.",
                expected="array",
                actual=type(value).__name__,
            )
            continue
        if field in _SINGLE_FIELDS and len(value) != 1:
            _issue(
                report,
                "FIELD_CARDINALITY_INVALID",
                "error",
                path,
                "단일 값 필드는 원소가 정확히 하나여야 합니다.",
                expected=1,
                actual=len(value),
            )
            continue
        if field in ("element_mapping", "result_pairs", "caution_points", "differentiation_suggestions"):
            if field == "differentiation_suggestions" and len(value) != 3:
                _issue(
                    report,
                    "FIELD_CARDINALITY_INVALID",
                    "review",
                    path,
                    "차별성 서술 제안은 MVP 규격에 따라 3개여야 합니다.",
                    expected=3,
                    actual=len(value),
                )
            for index, item in enumerate(value):
                item_path = f"{path}[{index}]"
                if not isinstance(item, str):
                    _issue(
                        report,
                        "FIELD_TYPE_INVALID",
                        "error",
                        item_path,
                        "배열 원소는 문자열이어야 합니다.",
                        expected="string",
                        actual=type(item).__name__,
                    )
                elif not item.strip():
                    _issue(
                        report,
                        "FIELD_EMPTY",
                        "error",
                        item_path,
                        "문자열이 비어 있습니다.",
                    )
        elif field == "overlap_level":
            if value and value[0] not in _OVERLAP_LEVELS:
                _issue(
                    report,
                    "FIELD_VALUE_INVALID",
                    "error",
                    path,
                    "overlap_level 허용값이 아닙니다.",
                    expected=sorted(_OVERLAP_LEVELS),
                    actual=value[0] if isinstance(value[0], str) else type(value[0]).__name__,
                )
        elif field == "llm_score":
            if value:
                score = _parse_number(value[0])
                if score is None or not 0 <= score <= 100:
                    _issue(
                        report,
                        "NUMBER_INVALID",
                        "error",
                        path,
                        "llm_score는 bool이 아닌 유한 숫자 0~100이어야 합니다.",
                        expected="finite number in [0, 100]",
                        actual=type(value[0]).__name__ if score is None else score,
                    )
        elif field in ("summary", "related_work_draft") and value:
            if not isinstance(value[0], str):
                _issue(
                    report,
                    "FIELD_TYPE_INVALID",
                    "error",
                    f"{path}[0]",
                    "단일 설명 필드 원소는 문자열이어야 합니다.",
                    expected="string",
                    actual=type(value[0]).__name__,
                )
            elif not value[0].strip():
                _issue(
                    report,
                    "FIELD_EMPTY",
                    "error",
                    f"{path}[0]",
                    "필수 설명 필드가 비어 있습니다.",
                )


def _expected_items(
    expected_items: Any,
    report: dict[str, Any],
) -> tuple[list[str] | None, list[tuple[str, str]] | None]:
    # 비교 결과 자체에서 기대 목록을 만들지 않는다. 독립 입력이 있어야 누락을 찾을 수 있다.
    if expected_items is None:
        _not_checked(
            report,
            "EXPECTED_ITEMS_UNAVAILABLE",
            "expected_items",
            "독립적인 비교 대상 목록이 없어 누락과 범위 밖 항목을 확정할 수 없습니다.",
        )
        _issue(
            report,
            "EXPECTED_ITEMS_UNAVAILABLE",
            "review",
            "expected_items",
            "비교 대상 목록이 전달되지 않아 커버리지를 확정할 수 없습니다.",
        )
        return None, None
    if not isinstance(expected_items, Mapping):
        _issue(
            report,
            "INPUT_TYPE_INVALID",
            "error",
            "expected_items",
            "expected_items는 mappings와 result_pairs를 포함하는 객체여야 합니다.",
            expected="object",
            actual=type(expected_items).__name__,
        )
        return None, None

    parsed: list[Any] = []
    for name, pattern in (("mappings", _ID_PATTERNS["M"]),):
        if name not in expected_items:
            _issue(
                report,
                "EXPECTED_ITEMS_INCOMPLETE",
                "review",
                f"expected_items.{name}",
                "예상 M 항목 목록이 없어 해당 커버리지를 검사할 수 없습니다.",
            )
            _not_checked(report, "EXPECTED_MAPPINGS_UNAVAILABLE", f"expected_items.{name}", "예상 M 항목 목록이 없습니다.")
            parsed.append(None)
            continue
        values = expected_items[name]
        if not _is_sequence(values):
            _issue(
                report,
                "FIELD_TYPE_INVALID",
                "error",
                f"expected_items.{name}",
                "예상 항목은 배열이어야 합니다.",
                expected="array",
                actual=type(values).__name__,
            )
            parsed.append(None)
            continue
        ids: list[str] = []
        for index, identifier in enumerate(values):
            if not isinstance(identifier, str) or not pattern.fullmatch(identifier):
                _issue(
                    report,
                    "IDENTIFIER_FORMAT_INVALID",
                    "error",
                    f"expected_items.{name}[{index}]",
                    "예상 M 항목 식별번호 형식이 올바르지 않습니다.",
                    expected="M<숫자>",
                    actual=identifier if isinstance(identifier, str) else type(identifier).__name__,
                )
            else:
                ids.append(identifier)
        duplicates = sorted(item for item, count in Counter(ids).items() if count > 1)
        for identifier in duplicates:
            _issue(
                report,
                "EXPECTED_ITEM_DUPLICATE",
                "error",
                f"expected_items.{name}",
                "예상 비교 목록 안에서 항목이 중복되었습니다.",
                item_id=identifier,
            )
        parsed.append(ids)

    if "result_pairs" not in expected_items:
        _issue(
            report,
            "EXPECTED_ITEMS_INCOMPLETE",
            "review",
            "expected_items.result_pairs",
            "예상 정량 비교 쌍 목록이 없어 누락 검사를 수행할 수 없습니다.",
        )
        _not_checked(report, "EXPECTED_RESULT_PAIRS_UNAVAILABLE", "expected_items.result_pairs", "예상 정량 비교 쌍 목록이 없습니다.")
        parsed.append(None)
    else:
        values = expected_items["result_pairs"]
        if not _is_sequence(values):
            _issue(
                report,
                "FIELD_TYPE_INVALID",
                "error",
                "expected_items.result_pairs",
                "예상 정량 비교 쌍은 배열이어야 합니다.",
                expected="array",
                actual=type(values).__name__,
            )
            parsed.append(None)
        else:
            pairs: list[tuple[str, str]] = []
            for index, pair in enumerate(values):
                if (
                    not _is_sequence(pair)
                    or len(pair) != 2
                    or not isinstance(pair[0], str)
                    or not isinstance(pair[1], str)
                    or not _ID_PATTERNS["R-M"].fullmatch(pair[0])
                    or not _ID_PATTERNS["R-P"].fullmatch(pair[1])
                ):
                    _issue(
                        report,
                        "EXPECTED_PAIR_FORMAT_INVALID",
                        "error",
                        f"expected_items.result_pairs[{index}]",
                        "예상 비교 쌍은 [R-M번호, R-P번호] 형식이어야 합니다.",
                    )
                    continue
                pairs.append((pair[0], pair[1]))
            duplicates = sorted(pair for pair, count in Counter(pairs).items() if count > 1)
            for pair in duplicates:
                _issue(
                    report,
                    "EXPECTED_ITEM_DUPLICATE",
                    "error",
                    "expected_items.result_pairs",
                    "예상 정량 비교 쌍이 중복되었습니다.",
                    item_id=f"{pair[0]}~{pair[1]}",
                )
            parsed.append(pairs)
    return parsed[0], parsed[-1]


def _check_mapping_evidence(
    mapping: dict[str, Any],
    m_index: dict[str, Mapping[str, Any]] | None,
    p_index: dict[str, Mapping[str, Any]] | None,
    report: dict[str, Any],
    index: int,
) -> None:
    # ID와 섹션 표기 같은 형식은 확인하지만, 인용 내용의 의미상 타당성은 판정하지 않는다.
    item_id = mapping["item_id"]
    verdict = mapping["verdict"]
    path = f"comparison_result.element_mapping[{index}]"
    if verdict not in _VERDICTS:
        _issue(
            report,
            "MAPPING_VERDICT_INVALID",
            "review",
            f"{path}.verdict",
            "판정이 MVP 허용값에 없어 확인이 필요합니다.",
            item_id=item_id,
            expected=sorted(_VERDICTS),
            actual=verdict[:80],
        )
        return

    if m_index is None or p_index is None:
        _not_checked(
            report,
            "MAPPING_REFERENCES_UNCHECKED",
            path,
            "독립적인 M/P 원본 목록이 모두 전달되지 않았습니다.",
        )
        return
    if item_id not in m_index:
        _issue(
            report,
            "SOURCE_REFERENCE_UNKNOWN",
            "error",
            path,
            "비교 결과가 원본 M 목록에 없는 항목을 참조합니다.",
            item_id=item_id,
        )
        return

    duplicate_prior_ids = sorted(
        prior_id for prior_id, count in Counter(mapping["prior_ids"]).items() if count > 1
    )
    for prior_id in duplicate_prior_ids:
        _issue(
            report,
            "P_REFERENCE_DUPLICATE",
            "error",
            f"{path}.prior_ids",
            "하나의 대응 행 안에서 같은 P 식별번호가 중복되었습니다.",
            item_id=prior_id,
        )
    if p_index is not None:
        for prior_id in mapping["prior_ids"]:
            if prior_id not in p_index:
                _issue(
                    report,
                    "SOURCE_REFERENCE_UNKNOWN",
                    "error",
                    f"{path}.prior_ids",
                    "비교 결과가 원본 P 목록에 없는 항목을 참조합니다.",
                    item_id=prior_id,
                )

    if verdict in ("일치", "유사"):
        if not mapping["prior_ids"]:
            _issue(
                report,
                "MATCH_WITHOUT_PRIOR_REFERENCE",
                "review",
                path,
                "일치·유사 판정에 기존 논문 P 식별번호가 없습니다.",
                item_id=item_id,
            )
        # "P[3.2,3.3]"처럼 대괄호 하나에 여러 섹션을 쉼표로 적는 경우도 섹션별로 나눈다.
        m_sections = [s.strip() for group in re.findall(r"M\[([^\]]+)\]", mapping["evidence"]) for s in group.split(",") if s.strip()]
        p_sections = [s.strip() for group in re.findall(r"P\[([^\]]+)\]", mapping["evidence"]) for s in group.split(",") if s.strip()]
        # P 섹션은 최소 1개 있어야 한다. 여러 P가 같은 섹션이면 섹션 하나로 함께 인용할 수 있다.
        if not m_sections or (mapping["prior_ids"] and not p_sections):
            _issue(
                report,
                "EVIDENCE_SECTION_MISSING",
                "review",
                f"{path}.evidence",
                "일치·유사 판정의 M/P 섹션 근거가 누락되었습니다.",
                item_id=item_id,
            )
        else:
            source_m_section = m_index[item_id].get("section")
            if source_m_section is None:
                _not_checked(report, "M_SECTION_UNAVAILABLE", f"source_records.M.{item_id}.section", "원본 M 레코드에 섹션 정보가 없습니다.")
            elif str(source_m_section).strip() not in {sec.strip() for sec in m_sections}:
                _issue(
                    report,
                    "EVIDENCE_SECTION_MISMATCH",
                    "review",
                    f"{path}.evidence",
                    "인용한 M 섹션과 원본 요소의 섹션 태그가 다릅니다.",
                    item_id=item_id,
                    expected=str(source_m_section),
                    actual=m_sections[0],
                )
            referenced_sections = {
                str(p_index[pid].get("section")).strip()
                for pid in mapping["prior_ids"]
                if pid in p_index and p_index[pid].get("section") is not None
            }
            if referenced_sections:
                for cited_section in p_sections:
                    if cited_section.strip() not in referenced_sections:
                        _issue(
                            report,
                            "EVIDENCE_SECTION_MISMATCH",
                            "review",
                            f"{path}.evidence",
                            "인용한 P 섹션이 대응한 P 요소들의 섹션 태그에 없습니다.",
                            item_id=item_id,
                            expected=sorted(referenced_sections),
                            actual=cited_section,
                        )
            elif mapping["prior_ids"]:
                _not_checked(report, "P_SECTION_UNAVAILABLE", f"{path}.evidence", "대응한 P 레코드에 섹션 정보가 없습니다.")
    elif verdict == "없음":
        if mapping["prior_ids"]:
            _issue(
                report,
                "NO_MATCH_HAS_PRIOR_REFERENCE",
                "review",
                path,
                "없음 판정과 P 대응번호가 함께 있어 범위를 확인해야 합니다.",
                item_id=item_id,
            )
        scope_text = mapping["evidence"]
        if "검토 범위" not in scope_text:
            _issue(
                report,
                "NO_MATCH_SCOPE_MISSING",
                "review",
                f"{path}.evidence",
                "없음 판정에 기존 논문의 검토 범위가 명시되지 않았습니다.",
                item_id=item_id,
            )
        elif p_index is not None:
            covered = _scope_ids(scope_text)
            unknown = sorted(covered - set(p_index))
            if unknown:
                # 존재하지 않는 P를 검토 범위에 적었다면 다른 입력(예전 PDF)을 보고 판정했을 수 있다.
                _issue(
                    report,
                    "NO_MATCH_SCOPE_UNKNOWN",
                    "review",
                    f"{path}.evidence",
                    "없음 판정의 검토 범위에 원본에 없는 P 번호가 있어 다른 입력을 보고 판정했을 수 있습니다.",
                    item_id=item_id,
                    actual=unknown,
                )
            elif not covered or not set(p_index).issubset(covered):
                _issue(
                    report,
                    "NO_MATCH_SCOPE_INCOMPLETE",
                    "review",
                    f"{path}.evidence",
                    "없음 판정의 검토 범위가 원본 P 목록 전체를 포함하는지 확인할 수 없습니다.",
                    item_id=item_id,
                )
    elif verdict == "확인필요" and not mapping["explanation"].strip():
        _issue(
            report,
            "REVIEW_REASON_MISSING",
            "review",
            f"{path}.explanation",
            "확인필요 판정의 설명이 비어 있습니다.",
            item_id=item_id,
        )
    elif verdict == "확인필요":
        _issue(
            report,
            "MAPPING_NEEDS_REVIEW",
            "review",
            path,
            "Compare Agent가 이 대응을 확인필요로 표시했습니다.",
            item_id=item_id,
        )


def _scope_ids(scope: str) -> set[str]:
    # "P1~P4" 같은 no-match 검토 범위를 ID 집합으로 풀어 범위 누락을 검사한다.
    identifiers = set(re.findall(r"P\d+", scope))
    for start, end in re.findall(r"P(\d+)\s*[~\-]\s*P?(\d+)", scope):
        lower, upper = int(start), int(end)
        if lower <= upper and upper - lower <= 10000:
            identifiers.update(f"P{number}" for number in range(lower, upper + 1))
    return identifiers


def _check_numeric_pair(
    pair: tuple[str, str],
    rm_index: dict[str, Mapping[str, Any]] | None,
    rp_index: dict[str, Mapping[str, Any]] | None,
    conversions: Mapping[tuple[str, str], float],
    report: dict[str, Any],
    item_index: int,
) -> dict[str, Any]:
    # 같은 지표·데이터셋·조건·방향과 해석 가능한 단위가 확인될 때만 수치를 비교한다.
    rm_id, rp_id = pair
    checked: dict[str, Any] = {
        "my_result_id": rm_id,
        "prior_result_id": rp_id,
        "outcome": "비교 불가",
        "reason": None,
        "absolute_difference": None,
        "absolute_difference_unit": None,
        "relative_change_percent": None,
        "comparison_unit": None,
    }
    path = f"comparison_result.result_pairs[{item_index}]"
    if rm_index is None or rp_index is None:
        checked["reason"] = "원본 실험 결과가 전달되지 않았습니다."
        _not_checked(report, "NUMERIC_SOURCE_UNAVAILABLE", "source_records.R-M/source_records.R-P", checked["reason"])
        _issue(report, "NUMERIC_SOURCE_UNAVAILABLE", "review", path, checked["reason"], item_id=f"{rm_id}~{rp_id}")
        return checked
    if rm_id not in rm_index or rp_id not in rp_index:
        missing = rm_id if rm_id not in rm_index else rp_id
        _issue(
            report,
            "SOURCE_REFERENCE_UNKNOWN",
            "error",
            path,
            "정량 비교가 원본 실험 결과 목록에 없는 번호를 참조합니다.",
            item_id=missing,
        )
        checked["reason"] = "원본 실험 결과에 없는 번호입니다."
        return checked

    mine, prior = rm_index[rm_id], rp_index[rp_id]
    checked_ids = f"{rm_id}~{rp_id}"
    for field in ("dataset", "metric"):
        a, b = mine.get(field), prior.get(field)
        if not isinstance(a, str) or not a.strip() or not isinstance(b, str) or not b.strip():
            checked["reason"] = f"{field} 정보가 비어 있습니다."
            _issue(report, "RESULT_CONDITION_UNAVAILABLE", "review", f"source_records.{field}", checked["reason"], item_id=checked_ids)
            return checked
        if a.strip() != b.strip():
            checked["reason"] = f"데이터셋 또는 지표 {field}가 다릅니다."
            _issue(report, "RESULT_CONDITION_MISMATCH", "review", f"source_records.{field}", checked["reason"], item_id=checked_ids)
            return checked

    if "conditions" not in mine or "conditions" not in prior:
        checked["reason"] = "실험 조건 자료가 부족합니다."
        _issue(report, "RESULT_CONDITION_UNAVAILABLE", "review", "source_records.conditions", checked["reason"], item_id=checked_ids)
        return checked
    if not isinstance(mine["conditions"], Mapping) or not isinstance(prior["conditions"], Mapping):
        checked["reason"] = "실험 조건은 객체여야 합니다."
        _issue(report, "FIELD_TYPE_INVALID", "error", "source_records.conditions", checked["reason"], item_id=checked_ids)
        return checked
    if mine["conditions"] != prior["conditions"]:
        checked["reason"] = "실험 조건이 달라 수치를 직접 비교할 수 없습니다."
        _issue(report, "RESULT_CONDITION_MISMATCH", "review", "source_records.conditions", checked["reason"], item_id=checked_ids)
        return checked

    direction = mine.get("direction")
    if direction not in ("↑", "↓") or prior.get("direction") not in ("↑", "↓"):
        checked["reason"] = "비교 방향(↑/↓)이 불명확합니다."
        _issue(report, "RESULT_DIRECTION_UNAVAILABLE", "review", "source_records.direction", checked["reason"], item_id=checked_ids)
        return checked
    if direction != prior.get("direction"):
        checked["reason"] = "두 실험의 최적화 방향이 다릅니다."
        _issue(report, "RESULT_DIRECTION_MISMATCH", "review", "source_records.direction", checked["reason"], item_id=checked_ids)
        return checked

    my_unit, prior_unit = mine.get("unit"), prior.get("unit")
    if not isinstance(my_unit, str) or not my_unit.strip() or not isinstance(prior_unit, str) or not prior_unit.strip():
        checked["reason"] = "수치 단위가 비어 있습니다."
        _issue(report, "RESULT_UNIT_UNAVAILABLE", "review", "source_records.unit", checked["reason"], item_id=checked_ids)
        return checked
    my_unit, prior_unit = my_unit.strip(), prior_unit.strip()
    my_value, prior_value = _parse_number(mine.get("value")), _parse_number(prior.get("value"))
    if my_value is None or prior_value is None:
        checked["reason"] = "원본 수치가 유한한 숫자로 확인되지 않습니다."
        _issue(report, "RESULT_VALUE_INVALID", "review", "source_records.value", checked["reason"], item_id=checked_ids)
        return checked

    comparison_unit = prior_unit
    # 기본 단위 변환은 추정하지 않고 호출자가 명시적으로 제공한 배율만 적용한다.
    if my_unit == prior_unit:
        converted_my = my_value
    elif (my_unit, prior_unit) in conversions:
        converted_my = my_value * conversions[(my_unit, prior_unit)]
    elif (prior_unit, my_unit) in conversions:
        comparison_unit = my_unit
        converted_my = my_value
        prior_value *= conversions[(prior_unit, my_unit)]
    else:
        checked["reason"] = "단위 조합에 대해 명시된 변환 규칙이 없습니다."
        _issue(report, "UNIT_CONVERSION_UNSUPPORTED", "review", "source_records.unit", checked["reason"], item_id=checked_ids, expected=prior_unit, actual=my_unit)
        return checked
    if not math.isfinite(converted_my) or not math.isfinite(prior_value):
        checked["reason"] = "단위 변환 후 수치가 유한하지 않습니다."
        _issue(report, "RESULT_VALUE_INVALID", "review", "source_records.value", checked["reason"], item_id=checked_ids)
        return checked
    checked["comparison_unit"] = comparison_unit

    # 0 기준은 상대 변화율을 정의할 수 없고, 50배 이상 차이는 단위 오기 가능성을 검토한다.
    low, high = sorted((abs(converted_my), abs(prior_value)))
    if prior_value == 0:
        checked["reason"] = "기준 수치가 0이므로 상대 변화율을 계산하지 않았습니다."
        _issue(report, "RELATIVE_CHANGE_BASELINE_ZERO", "review", "source_records.value", checked["reason"], item_id=checked_ids)
    if low == 0 and high != 0 or (low != 0 and high / low >= 50):
        checked["reason"] = "두 수치의 차이가 50배 이상이거나 비율을 계산할 수 없어 단위 불일치 가능성이 있습니다."
        _issue(report, "RESULT_RATIO_SUSPECTED_UNIT", "review", "source_records.value", checked["reason"], item_id=checked_ids)
        return checked

    difference = converted_my - prior_value
    if not math.isfinite(difference):
        checked["reason"] = "수치 차이가 유한한 숫자로 표현되지 않아 비교 결과를 확정할 수 없습니다."
        _issue(report, "RESULT_VALUE_INVALID", "review", "source_records.value", checked["reason"], item_id=checked_ids)
        return checked
    if direction == "↑":
        outcome = "우세" if difference > 0 else "열세" if difference < 0 else "동일"
    else:
        outcome = "우세" if difference < 0 else "열세" if difference > 0 else "동일"
    checked["outcome"] = outcome
    checked["absolute_difference"] = difference
    # 퍼센트 값의 절대 차이는 상대 변화율과 다른 단위(%p)로 보고한다.
    checked["absolute_difference_unit"] = "%p" if comparison_unit == "%" else comparison_unit
    if prior_value != 0:
        relative_change = difference / prior_value * 100
        if math.isfinite(relative_change):
            checked["relative_change_percent"] = relative_change
        else:
            checked["reason"] = "상대 변화율이 유한한 숫자로 표현되지 않아 계산하지 않았습니다."
            _issue(report, "RELATIVE_CHANGE_INVALID", "review", "source_records.value", checked["reason"], item_id=checked_ids)
    return checked


def _conversion_map(value: Any) -> dict[tuple[str, str], float]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("supported_unit_conversions는 (원본 단위, 목표 단위): 배율 mapping이어야 합니다.")
    normalized: dict[tuple[str, str], float] = {}
    for units, factor in value.items():
        if (
            not isinstance(units, tuple)
            or len(units) != 2
            or not all(isinstance(unit, str) and unit.strip() for unit in units)
        ):
            raise ValueError("단위 변환 키는 비어 있지 않은 두 단위 문자열의 튜플이어야 합니다.")
        number = _parse_number(factor)
        if number is None or number <= 0:
            raise ValueError("단위 변환 배율은 bool이 아닌 양의 유한 숫자여야 합니다.")
        normalized[(units[0].strip(), units[1].strip())] = number
    return normalized


def validate_comparison(
    comparison_result: Mapping[str, Any],
    source_records: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    expected_items: Mapping[str, Sequence[Any]] | None = None,
    *,
    supported_unit_conversions: Mapping[tuple[str, str], float] | None = None,
) -> dict[str, Any]:
    """Validate one Compare Agent result and return a separate JSON-safe report.

    ``source_records`` and ``expected_items`` are independent evidence/scope
    inputs. This function never repairs, reassigns identifiers, or mutates any
    input. An explicitly supplied unit conversion is a positive multiplier
    applied to the first unit to express it in the second unit.
    """
    # 매 호출마다 새 보고서를 만든다. 원본 인자나 Compare Agent 결과는 수정하지 않는다.
    conversions = _conversion_map(supported_unit_conversions)
    report: dict[str, Any] = {
        "status": "PASSED",
        "block_final_decision": False,
        "issues": [],
        "coverage": {
            "mappings": _coverage(None, []),
            "result_pairs": _coverage(None, []),
        },
        "numeric_checks": [],
        "not_checked": [],
    }
    _not_checked(
        report,
        "SEMANTIC_VALIDITY_NOT_CHECKED",
        "comparison_result.element_mapping",
        "기법의 의미상 동일성, 원문 주장 전체의 참·거짓, 근거의 충분성은 규칙 기반으로 판정하지 않습니다.",
    )

    _validate_schema(comparison_result, report)
    mapping_lines = comparison_result.get("element_mapping") if isinstance(comparison_result, Mapping) else None
    result_lines = comparison_result.get("result_pairs") if isinstance(comparison_result, Mapping) else None
    if not _is_sequence(mapping_lines):
        mapping_lines = []
    if not _is_sequence(result_lines):
        result_lines = []

    if source_records is not None and not isinstance(source_records, Mapping):
        _issue(
            report,
            "INPUT_TYPE_INVALID",
            "error",
            "source_records",
            "원본 레코드는 M/P/R 목록을 포함하는 객체여야 합니다.",
            expected="object",
            actual=type(source_records).__name__,
        )
        source_records = None

    m_index = _record_index(source_records, "M", report)
    p_index = _record_index(source_records, "P", report)
    rm_index = _record_index(source_records, "R-M", report)
    rp_index = _record_index(source_records, "R-P", report)
    if source_records is None:
        _issue(
            report,
            "SOURCE_RECORDS_UNAVAILABLE",
            "review",
            "source_records",
            "독립적인 원본 추출 자료가 없어 식별번호·근거·수치 대조를 완료할 수 없습니다.",
        )
        _not_checked(report, "SOURCE_RECORDS_UNAVAILABLE", "source_records", "원본 근거 목록이 전달되지 않았습니다.")

    expected_mappings, expected_pairs = _expected_items(expected_items, report)
    parsed_mappings: list[dict[str, Any]] = []
    observed_mappings: list[str] = []
    for index, line in enumerate(mapping_lines):
        if not isinstance(line, str):
            continue
        mapping = _parse_mapping(line)
        if mapping is None:
            _issue(
                report,
                "MAPPING_FORMAT_INVALID",
                "error",
                f"comparison_result.element_mapping[{index}]",
                "대응 행 형식이 'M번호 ↔ P번호 | 판정 | 근거 | 설명'과 맞지 않습니다.",
            )
            continue
        parsed_mappings.append(mapping)
        observed_mappings.append(mapping["item_id"])
        _check_mapping_evidence(mapping, m_index, p_index, report, index)
    report["coverage"]["mappings"] = _coverage(expected_mappings, observed_mappings)
    if expected_mappings is not None:
        source_m_ids = set(m_index) if m_index is not None else None
        if source_m_ids is not None:
            missing_from_expected = sorted(source_m_ids - set(expected_mappings))
            for item_id in missing_from_expected:
                _issue(
                    report,
                    "EXPECTED_ITEMS_INCOMPLETE",
                    "error",
                    "expected_items.mappings",
                    "독립 원본의 M 항목이 예상 비교 대상 목록에서 빠졌습니다.",
                    item_id=item_id,
                )
        for item_id in report["coverage"]["mappings"]["missing"]:
            _issue(
                report,
                "MAPPING_MISSING",
                "error",
                "comparison_result.element_mapping",
                "필수 비교 대상 M 항목의 대응 행이 없습니다.",
                item_id=item_id,
            )
        for item_id in report["coverage"]["mappings"]["duplicates"]:
            _issue(
                report,
                "MAPPING_DUPLICATE",
                "error",
                "comparison_result.element_mapping",
                "같은 M 항목의 대응 행이 중복되었습니다.",
                item_id=item_id,
            )
        for item_id in report["coverage"]["mappings"]["out_of_scope"]:
            _issue(
                report,
                "MAPPING_OUT_OF_SCOPE",
                "error",
                "comparison_result.element_mapping",
                "예상 목록에 없는 M 항목이 비교 결과에 포함되었습니다.",
                item_id=item_id,
            )
    else:
        _not_checked(report, "MAPPING_COVERAGE_UNCHECKED", "comparison_result.element_mapping", "예상 M 목록이 없어 누락·범위 검사를 수행할 수 없습니다.")

    verdicts_by_item: dict[str, set[str]] = {}
    for mapping in parsed_mappings:
        verdicts_by_item.setdefault(mapping["item_id"], set()).add(mapping["verdict"])
    for item_id, verdicts in verdicts_by_item.items():
        valid_verdicts = verdicts & _VERDICTS
        if len(valid_verdicts) > 1:
            _issue(
                report,
                "MAPPING_CONFLICT",
                "review",
                "comparison_result.element_mapping",
                "같은 M 항목에 서로 다른 판정이 있어 확인이 필요합니다.",
                item_id=item_id,
                actual=sorted(valid_verdicts),
            )

    parsed_pairs: list[tuple[str, str]] = []
    for index, line in enumerate(result_lines):
        if not isinstance(line, str):
            continue
        pair = _parse_result_pair(line)
        if pair is None:
            _issue(
                report,
                "RESULT_PAIR_FORMAT_INVALID",
                "error",
                f"comparison_result.result_pairs[{index}]",
                "정량 비교 쌍 형식이 'R-M번호 ~ R-P번호 | 조건 | 설명'과 맞지 않습니다.",
            )
            continue
        parsed_pairs.append(pair)
    report["coverage"]["result_pairs"] = _coverage(expected_pairs, parsed_pairs)
    if expected_pairs is not None:
        for pair in report["coverage"]["result_pairs"]["missing"]:
            _issue(
                report,
                "RESULT_PAIR_MISSING",
                "review",
                "comparison_result.result_pairs",
                "필수 정량 비교 쌍이 결과에서 누락되었습니다.",
                item_id=f"{pair[0]}~{pair[1]}",
            )
        for pair in report["coverage"]["result_pairs"]["duplicates"]:
            _issue(
                report,
                "RESULT_PAIR_DUPLICATE",
                "error",
                "comparison_result.result_pairs",
                "정량 비교 쌍이 중복되었습니다.",
                item_id=f"{pair[0]}~{pair[1]}",
            )
        for pair in report["coverage"]["result_pairs"]["out_of_scope"]:
            _issue(
                report,
                "RESULT_PAIR_OUT_OF_SCOPE",
                "review",
                "comparison_result.result_pairs",
                "예상 목록에 없는 정량 비교 쌍이 결과에 포함되었습니다.",
                item_id=f"{pair[0]}~{pair[1]}",
            )
    else:
        _not_checked(report, "RESULT_PAIR_COVERAGE_UNCHECKED", "comparison_result.result_pairs", "예상 정량 비교 쌍 목록이 없어 누락·범위 검사를 수행할 수 없습니다.")

    for index, pair in enumerate(parsed_pairs):
        report["numeric_checks"].append(
            _check_numeric_pair(pair, rm_index, rp_index, conversions, report, index)
        )

    # 오류가 검토 필요보다 우선하며, 둘 중 하나라도 있으면 최종 결정을 막는다.
    errors = any(issue["severity"] == "error" for issue in report["issues"])
    reviews = any(issue["severity"] == "review" for issue in report["issues"])
    report["status"] = "FAILED" if errors else "NEEDS_REVIEW" if reviews else "PASSED"
    report["block_final_decision"] = report["status"] != "PASSED"
    return report



##################################################
# PriorScope 진입점: app.py / service.py가 부르는 함수
##################################################

# 등급 경계값(%). 설계서의 등급 기준표와 다르면 이 두 숫자만 바꾼다.
HIGH_THRESHOLD = 70.0
MEDIUM_THRESHOLD = 30.0

# 임베딩 유사도 강등 임계값 (멘토링 10/27). eval/calibrate_similarity.py 로 정한 값을 .env 에 넣는다.
# 정하지 않으면(None) 유사도는 보고만 하고 판정은 바꾸지 않는다.
_sim_env = os.getenv("SIMILARITY_DEMOTE_THRESHOLD")
SIMILARITY_DEMOTE_THRESHOLD: float | None = float(_sim_env) if _sim_env else None

# 판정별 점수. 확인필요는 0~1 사이 어디든 될 수 있으므로 범위로 계산한다.
_VERDICT_SCORE = {"일치": 1.0, "유사": 0.5, "없음": 0.0}

_LEVEL_NAMES = {"High": "High Overlap", "Medium": "Medium Overlap", "Low": "Low Overlap"}
_MAPPING_PATH = re.compile(r"element_mapping\[(\d+)\]")


def _level_of(percent: float) -> str:
    if percent >= HIGH_THRESHOLD:
        return _LEVEL_NAMES["High"]
    if percent >= MEDIUM_THRESHOLD:
        return _LEVEL_NAMES["Medium"]
    return _LEVEL_NAMES["Low"]


# ---------------------------------------------------------------
# 실험 결과 표기 정규화
# Studio가 같은 지표를 "top-1 accuracy" / "Top-1", "Recall@1" / "R@1"처럼
# 다르게 적어도 같은 지표로 묶는다. 화면에는 원문(*_raw)을 그대로 보여준다.
# 새 표기를 발견하면 아래 사전에만 한 줄 추가하면 된다. (키는 _compact() 결과)
# ---------------------------------------------------------------
_METRIC_ALIASES = {
    "top1accuracy": "top1",
    "top1acc": "top1",
    "acc@1": "top1",
    "top5accuracy": "top5",
    "top5acc": "top5",
    "acc@5": "top5",
    "accuracy": "acc",
    "averageprecision": "ap",
    "meanaverageprecision": "map",
    "f1score": "f1",
    "f1": "f1",
}
_DATASET_ALIASES = {
    # 예: "imagenet1k": "in1k", "imagenet": "in1k"  (팀에서 확인 후 추가)
    "audioset": "asa",
    "as": "asa",
}
_RECALL_PATTERN = re.compile(r"^(?:recall|r)@(\d+)$")

# 근거 위치로 인정하는 형식: [Table 2], [Tab. 3a], [표 2], [Fig. 4], [3.2]
_LOCATION_PATTERN = re.compile(
    r"^\[\s*(?:(?:table|tab\.?|표|figure|fig\.?|그림)\s*)?\d+(?:\.\d+)*[a-z]?\s*\]$",
    re.IGNORECASE,
)


def _compact(text: Any) -> str:
    # 대소문자·공백·하이픈·밑줄·마침표 차이를 없앤다. "Top-1 Acc." -> "top1acc"
    return re.sub(r"[\s\-_.]+", "", str(text or "")).lower()


def _canon_metric(text: Any) -> str:
    key = _compact(text)
    recall = _RECALL_PATTERN.match(key)
    if recall:
        return f"r@{recall.group(1)}"
    return _METRIC_ALIASES.get(key, key)


def _canon_dataset(text: Any) -> str:
    key = _compact(text)
    return _DATASET_ALIASES.get(key, key)


def _parse_result_record(entry: Mapping[str, Any]) -> dict[str, Any]:
    # "데이터셋 | 방법·설정 | 지표 | 수치 | ↑ | [위치]" 문자열을 수치 비교용 레코드로 바꾼다.
    parts = [part.strip() for part in str(entry["text"]).split("|")]
    record: dict[str, Any] = {"id": entry["id"], "text": entry["text"]}
    if len(parts) < 5:
        return record  # 형식이 다르면 비교 정보 없이 둔다 -> 수치 비교는 '비교 불가'로 처리된다
    dataset, setting, metric, value, direction = parts[:5]
    number_text = value.replace("%", "").replace(",", "").strip()
    location = parts[5] if len(parts) > 5 else None
    canon_metric = _canon_metric(metric)
    record.update({
        # 비교에는 정규화된 값을, 화면에는 원문을 쓴다.
        "dataset": _canon_dataset(dataset),
        "metric": canon_metric,
        "dataset_raw": dataset,
        "metric_raw": metric,
        # 2열은 "방법 이름"(Fine-tuning (our) / IMAGEBIND)이라 양쪽이 같을 수 없다.
        # 그래서 동일 조건 여부는 코드가 문자열로 비교하지 않고,
        # Compare Agent의 result_pairs 판정(동일 조건/조건 다름)으로 따로 처리한다.
        "setting": setting,
        "conditions": {},
        "direction": direction,
        "value": number_text,
        # 같은 데이터셋·지표끼리만 비교하므로, 정규화된 지표 이름을 단위로 쓴다.
        "unit": "%" if "%" in value else canon_metric,
        "location": location,
        "location_valid": bool(location) and bool(_LOCATION_PATTERN.match(location)),
    })
    return record


def _expected_result_pairs(rm: list[dict[str, Any]], rp: list[dict[str, Any]]) -> list[list[str]]:
    # 코드가 독립적으로 계산한 "데이터셋과 지표가 같은 쌍". Compare Agent의 result_pairs와 대조한다.
    return [
        [a["id"], b["id"]]
        for a in rm
        for b in rp
        if a.get("dataset") and a.get("metric")
        and a.get("dataset") == b.get("dataset")
        and a.get("metric") == b.get("metric")
    ]


def _duplicate_results(records: list[dict[str, Any]]) -> dict[str, str]:
    # 데이터셋·지표·수치가 모두 같은 행은 ablation 표에서 반복 추출된 것으로 본다.
    # 번호(R-M3 등)는 builder와 맞아야 하므로 지우지 않고, "첫 행의 중복"으로 표시만 한다.
    seen: dict[tuple, str] = {}
    duplicates: dict[str, str] = {}
    for record in records:
        if not record.get("dataset"):
            continue
        key = (record["dataset"], record["metric"], record.get("value"))
        if key in seen:
            duplicates[record["id"]] = seen[key]
        else:
            seen[key] = record["id"]
    return duplicates


def _pair_labels(compare_result: Mapping[str, Any]) -> dict[tuple[str, str], str]:
    # result_pairs의 2열(동일 조건 / 조건 다름)을 쌍별로 읽는다.
    labels: dict[tuple[str, str], str] = {}
    lines = compare_result.get("result_pairs") if isinstance(compare_result, Mapping) else None
    for line in lines if _is_sequence(lines) else []:
        if not isinstance(line, str):
            continue
        parts = [part.strip() for part in line.split("|")]
        match = re.fullmatch(r"(R-M\d+)\s*~\s*(R-P\d+)", parts[0]) if parts else None
        if match:
            labels[match.groups()] = parts[1] if len(parts) == 3 else ""
    return labels


def _apply_pair_conditions(
    numeric_checks: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    labels: dict[tuple[str, str], str],
    duplicates: dict[str, str],
) -> None:
    # 의미 판단(조건이 같은가)은 Compare Agent가, 수치 판단은 코드가 한다.
    # 원칙대로 강등만 한다: '동일 조건'이 명시되지 않으면 '비교 불가'로 내린다.
    for check in numeric_checks:
        my_id, prior_id = check["my_result_id"], check["prior_result_id"]
        mine, prior = records.get(my_id, {}), records.get(prior_id, {})
        check.update({
            "dataset": mine.get("dataset_raw"),
            "my_metric": mine.get("metric_raw"),
            "prior_metric": prior.get("metric_raw"),
            "my_setting": mine.get("setting"),
            "prior_setting": prior.get("setting"),
            "my_value": mine.get("value"),
            "prior_value": prior.get("value"),
            "agent_condition": labels.get((my_id, prior_id), ""),
            "warnings": [],
        })
        label = check["agent_condition"]
        if check["outcome"] != "비교 불가" and "동일 조건" not in label:
            check.update({
                "outcome": "비교 불가",
                "reason": (
                    "Compare Agent가 실험 조건이 다르다고 판단했습니다."
                    if "조건 다름" in label
                    else "실험 조건이 같은지 Compare Agent가 명시하지 않았습니다."
                ),
                "absolute_difference": None,
                "absolute_difference_unit": None,
                "relative_change_percent": None,
            })
        for rid, record in ((my_id, mine), (prior_id, prior)):
            if record and not record.get("location_valid"):
                check["warnings"].append(f"{rid}의 근거 위치({record.get('location')})를 확인할 수 없습니다.")
            if rid in duplicates:
                check["warnings"].append(f"{rid}는 {duplicates[rid]}와 같은 결과의 중복 추출로 보입니다.")


def _first(data: Mapping[str, Any], key: str) -> Any:
    value = data.get(key) if isinstance(data, Mapping) else None
    if _is_sequence(value):
        return value[0] if value else None
    return value



##################################################
# 약점 리포트 (피드백 반영: "부족한 부분과 판단 이유를 근거와 함께")
##################################################

def derive_weaknesses(verified: Mapping[str, Any], ids: Mapping[str, Any]) -> dict[str, Any]:
    """검증 결과에서 '기존 논문 대비 부족할 수 있는 점'을 코드로 파생한다. LLM 관여 없음.

    1) prior_only: 어떤 M 요소의 대응에도 등장하지 않은 P 요소
       = 기존 논문에는 있는데 내 논문에서 다루지 않은 구성.
       확인필요 행에 등장한 P도 '다룬 것'으로 보고 빼서, 약점을 과장하지 않는다.
    2) inferior_results: 동일 조건이 확인된 쌍 중 내 수치가 낮은(열세) 실험.

    verified 는 validate() 결과(또는 예전 validated_result.json), ids 는 assign_ids() 결과.
    예전 결과 파일에도 쓸 수 있게 mappings / numeric_checks 만 사용한다.
    """
    mappings = verified.get("mappings") or []
    referenced = {pid for m in mappings for pid in (m.get("prior_ids") or [])}
    uncertain_without_prior = [
        m["id"] for m in mappings if m.get("final_verdict") == "확인필요" and not m.get("prior_ids")
    ]

    prior_only = [
        {
            "id": p["id"],
            "text": p["text"],
            "section": p.get("section"),
            "reason": "내 논문의 어떤 핵심 기술 요소(M)와도 대응되지 않았습니다.",
        }
        for p in ids.get("P", [])
        if p["id"] not in referenced
    ]

    rm_text = {r["id"]: r["text"] for r in ids.get("RM", [])}
    rp_text = {r["id"]: r["text"] for r in ids.get("RP", [])}
    inferior_results = []
    for check in verified.get("numeric_checks") or []:
        if check.get("outcome") != "열세":
            continue
        my_id, prior_id = check["my_result_id"], check["prior_result_id"]
        inferior_results.append({
            "my_result_id": my_id,
            "prior_result_id": prior_id,
            "my_text": rm_text.get(my_id, ""),
            "prior_text": rp_text.get(prior_id, ""),
            "dataset": check.get("dataset"),
            "metric": check.get("my_metric") or check.get("prior_metric"),
            "my_value": check.get("my_value"),
            "prior_value": check.get("prior_value"),
            "difference": check.get("absolute_difference"),
            "difference_unit": check.get("absolute_difference_unit"),
            "reason": "동일 조건에서 내 수치가 기존 논문보다 낮습니다.",
        })

    return {
        "prior_only": prior_only,
        "inferior_results": inferior_results,
        # 대응 판정이 빠진 M이 있으면 prior_only 목록이 실제보다 길 수 있다.
        "prior_only_complete": not uncertain_without_prior,
        "uncertain_without_prior": uncertain_without_prior,
        "counts": {"prior_only": len(prior_only), "inferior_results": len(inferior_results)},
    }



##################################################
# 임베딩 유사도 교차 검증 (멘토링 10/27)
##################################################

def _apply_similarity(
    mappings: list[dict[str, Any]],
    ids: Mapping[str, Any],
    similarity: Mapping[str, Any] | None,
    demote_threshold: float | None,
    report: dict[str, Any],
) -> dict[str, Any]:
    """similarity.py 결과를 M별 판정에 붙이고, 조건이 맞으면 '없음'을 '확인필요'로 강등한다."""
    threshold = demote_threshold if demote_threshold is not None else SIMILARITY_DEMOTE_THRESHOLD
    out: dict[str, Any] = {"available": False, "model": None, "threshold": threshold, "demoted": []}
    if not similarity:
        _not_checked(report, "SIMILARITY_UNAVAILABLE", "similarity", "임베딩 유사도 결과가 없어 교차 검증을 하지 않았습니다.")
        return out

    # 다른 실행의 similarity.json 이 섞이면 쓰지 않는다 (번호 짝 검사).
    m_ids = [m["id"] for m in ids["M"]]
    p_ids = [p["id"] for p in ids["P"]]
    if list(similarity.get("m_ids") or []) != m_ids or list(similarity.get("p_ids") or []) != p_ids:
        _not_checked(report, "SIMILARITY_MISMATCH", "similarity", "유사도 결과의 M·P 번호가 지금 논문 JSON과 달라 사용하지 않았습니다.")
        out["mismatch"] = True
        return out

    out.update({"available": True, "model": similarity.get("model"), "stats": similarity.get("stats")})
    if threshold is None:
        _not_checked(report, "SIMILARITY_THRESHOLD_UNSET", "similarity", "유사도 임계값이 정해지지 않아 점수만 보고하고 판정은 바꾸지 않았습니다.")

    matrix = similarity.get("matrix") or {}
    per_m = {row["id"]: row for row in similarity.get("per_m") or []}
    for mapping in mappings:
        row = per_m.get(mapping["id"])
        if not row:
            continue
        cited = [matrix.get(mapping["id"], {}).get(pid) for pid in mapping["prior_ids"]]
        cited = [c for c in cited if c is not None]
        mapping["similarity"] = {
            "best_p": row["best_p"],
            "max_score": row["max_score"],
            "top": row.get("top", []),
            "cited_max": max(cited) if cited else None,
        }
        if threshold is not None and mapping["final_verdict"] == "없음" and row["max_score"] >= threshold:
            mapping["final_verdict"] = "확인필요"
            mapping["demoted_reasons"] = list(mapping["demoted_reasons"]) + [
                f"LLM은 없음으로 판정했지만 임베딩 유사도가 높습니다 "
                f"({row['best_p']} {row['max_score']:.3f} ≥ 임계값 {threshold:.3f})."
            ]
            out["demoted"].append(mapping["id"])
            _issue(
                report,
                "SIMILARITY_DEMOTED",
                "review",
                "similarity",
                "LLM의 없음 판정과 임베딩 유사도가 어긋나 확인필요로 강등했습니다.",
                item_id=mapping["id"],
                actual=row["max_score"],
            )
    return out


def validate(
    my_paper: Mapping[str, Any],
    prior_paper: Mapping[str, Any],
    compare_result: Mapping[str, Any],
    similarity: Mapping[str, Any] | None = None,
    demote_threshold: float | None = None,
) -> dict[str, Any]:
    """세 JSON을 받아 화면에서 바로 쓸 검증 결과를 돌려준다.

    반환값
    - status / issues / not_checked: validate_comparison()의 검사 보고서
    - mappings: M 요소별 최종 판정(강등 반영)과 근거
    - coverage: 커버리지 범위(min~max %)와 확인필요 개수
    - final_level: 범위가 한 등급 안에 있으면 그 등급, 아니면 "판정 보류"
    - classify_level / classify_agrees: Compare Agent(Classify) 등급과 코드 계산 등급의 일치 여부
    - uncertain_items: 사람이 확인해야 할 M 요소 목록
    - numeric_checks: 데이터셋·지표가 같은 실험 쌍의 수치 비교
    """
    from ids import assign_ids  # builder와 같은 번호 규칙을 쓴다

    ids = assign_ids(my_paper, prior_paper)
    rm = [_parse_result_record(e) for e in ids["RM"]]
    rp = [_parse_result_record(e) for e in ids["RP"]]
    source_records = {"M": ids["M"], "P": ids["P"], "R-M": rm, "R-P": rp}
    expected_items = {
        "mappings": [m["id"] for m in ids["M"]],
        "result_pairs": _expected_result_pairs(rm, rp),
    }

    report = validate_comparison(compare_result, source_records, expected_items)

    # 정량 비교 후처리: 동일 조건 여부(에이전트 판정)·근거 위치·중복 추출을 반영한다.
    record_by_id = {r["id"]: r for r in rm + rp}
    duplicates = {**_duplicate_results(rm), **_duplicate_results(rp)}
    _apply_pair_conditions(report["numeric_checks"], record_by_id, _pair_labels(compare_result), duplicates)

    # 1) 대응 행별 문제를 모은다 (경로의 element_mapping[i]로 행을 찾는다)
    problems_by_row: dict[int, list[str]] = {}
    for issue in report["issues"]:
        match = _MAPPING_PATH.search(issue["path"])
        if match and issue["code"] != "MAPPING_NEEDS_REVIEW":
            problems_by_row.setdefault(int(match.group(1)), []).append(issue["message"])

    # 2) M 요소별 최종 판정을 만든다. 문제가 있으면 확인필요로 강등만 한다.
    lines = compare_result.get("element_mapping") if isinstance(compare_result, Mapping) else None
    lines = lines if _is_sequence(lines) else []
    rows_by_m: dict[str, dict[str, Any]] = {}
    for index, line in enumerate(lines):
        parsed = _parse_mapping(line) if isinstance(line, str) else None
        if parsed is None or parsed["item_id"] in rows_by_m:
            continue  # 형식 오류나 중복 행은 아래에서 '대응 없음 -> 확인필요'로 처리된다
        reasons = problems_by_row.get(index, [])
        agent_verdict = parsed["verdict"] if parsed["verdict"] in _VERDICTS else "확인필요"
        final_verdict = "확인필요" if reasons else agent_verdict
        rows_by_m[parsed["item_id"]] = {
            "prior_ids": parsed["prior_ids"],
            "agent_verdict": parsed["verdict"],
            "final_verdict": final_verdict,
            "evidence": parsed["evidence"],
            "explanation": parsed["explanation"],
            "demoted_reasons": reasons,
        }

    mappings: list[dict[str, Any]] = []
    for m in ids["M"]:
        row = rows_by_m.get(m["id"]) or {
            "prior_ids": [],
            "agent_verdict": None,
            "final_verdict": "확인필요",
            "evidence": "",
            "explanation": "",
            "demoted_reasons": ["Compare Agent가 이 요소의 대응을 작성하지 않았거나 형식이 맞지 않습니다."],
        }
        mappings.append({"id": m["id"], "text": m["text"], "section": m["section"], **row})

    # 2-1) 임베딩 유사도 교차 검증: LLM이 '없음'인데 코드 유사도가 높으면 확인필요로 강등만 한다.
    sim_report = _apply_similarity(mappings, ids, similarity, demote_threshold, report)
    if sim_report["demoted"]:
        # 유사도 강등은 validate_comparison() 이후에 생긴 이슈라 상태를 다시 계산한다.
        has_error = any(i["severity"] == "error" for i in report["issues"])
        report["status"] = "FAILED" if has_error else "NEEDS_REVIEW"
        report["block_final_decision"] = True

    # 3) 커버리지 범위와 등급
    total = len(mappings)
    known = sum(_VERDICT_SCORE.get(r["final_verdict"], 0.0) for r in mappings if r["final_verdict"] != "확인필요")
    uncertain = [r for r in mappings if r["final_verdict"] == "확인필요"]
    if total:
        coverage_min = round(known / total * 100, 1)
        coverage_max = round((known + len(uncertain)) / total * 100, 1)
        level_min, level_max = _level_of(coverage_min), _level_of(coverage_max)
        final_level = level_min if level_min == level_max else "판정 보류"
    else:
        coverage_min = coverage_max = None
        final_level = "판정 보류"

    classify_level = _first(compare_result, "overlap_level")
    classify_agrees = final_level != "판정 보류" and classify_level == final_level

    counts = Counter(r["final_verdict"] for r in mappings)
    result = {
        "status": report["status"],
        "final_level": final_level,
        "classify_level": classify_level,
        "classify_agrees": classify_agrees,
        "llm_score": _first(compare_result, "llm_score"),
        "coverage": {
            "min": coverage_min,
            "max": coverage_max,
            "uncertain_count": len(uncertain),
            "verdict_counts": {v: counts.get(v, 0) for v in ("일치", "유사", "없음", "확인필요")},
            "thresholds": {"high": HIGH_THRESHOLD, "medium": MEDIUM_THRESHOLD},
        },
        "mappings": mappings,
        "uncertain_items": [
            {"id": r["id"], "text": r["text"], "reasons": r["demoted_reasons"] or [r["explanation"]]}
            for r in uncertain
        ],
        "numeric_checks": report["numeric_checks"],
        "expected_result_pairs": expected_items["result_pairs"],
        "result_warnings": {
            "duplicates": duplicates,
            "invalid_locations": [r["id"] for r in rm + rp if r.get("dataset") and not r.get("location_valid")],
        },
        "issues": report["issues"],
        "not_checked": report["not_checked"],
    }
    result["similarity"] = sim_report
    result["weaknesses"] = derive_weaknesses(result, ids)
    return result
