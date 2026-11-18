"""Guard: every writer unit in the hte deployment documents its outputs."""

from pathlib import Path

from helao.helpers.readme_outputs import missing_outputs_sections

EXTRA: list[str] = []


def test_writer_units_document_outputs():
    root = Path(__file__).resolve().parents[1]
    assert missing_outputs_sections(root, EXTRA) == []
