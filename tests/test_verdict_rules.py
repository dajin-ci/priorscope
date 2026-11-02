"""판정 기준 문구가 세 곳에서 어긋나지 않고, Studio 제한을 넘지 않는지 확인한다."""
from pathlib import Path

import verdict_rules as v


def test_studio_texts_fit_byte_limit():
    for text in (v.STUDIO_ELEMENT_MAPPING, v.STUDIO_INSTRUCT):
        assert len(text.encode("utf-8")) <= v.STUDIO_LIMIT_BYTES


def test_compare_pdf_guide_carries_full_rules():
    import compare_builder
    guide = " ".join(compare_builder.GUIDE_LINES)
    assert "판정 기준" in guide and all(line in guide for line in v.rule_lines())


def test_studio_text_doc_matches_constants():
    doc = (Path(__file__).resolve().parent.parent / "agent_configs" / "STUDIO_COMPARE_TEXT.md").read_text(encoding="utf-8")
    assert v.STUDIO_ELEMENT_MAPPING in doc and v.STUDIO_INSTRUCT in doc
