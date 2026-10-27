"""PDF — guide trajets sécurisés et secteurs SSU."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prediction_shared.guide_content import build_guide_document


def _para(text: str, style) -> Any:
    from reportlab.platypus import Paragraph

    return Paragraph(text.replace("\n", "<br/>"), style)


def _table(rows: list[list[str]], col_widths: list[float] | None = None) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tbl


def generate_guide_pdf(output: Path, doc: dict[str, Any] | None = None) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import PageBreak, SimpleDocTemplate, Spacer

    doc = doc or build_guide_document()
    pdf = SimpleDocTemplate(str(output), pagesize=A4, title=doc["title"])
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"], fontSize=17, textColor=colors.HexColor("#1e3a5f")
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=12)
    body = styles["BodyText"]

    story: list[Any] = []
    story.append(_para(f"<b>{doc['title']}</b>", title_style))
    story.append(_para(f"<i>{doc['subtitle']}</i>", body))
    story.append(
        _para(
            f"Généré le {doc['generated_at']} — {doc['version']}",
            body,
        )
    )
    story.append(Spacer(1, 0.5 * cm))

    story.append(_para("<b>Chaîne de traitement</b>", h2))
    for step in doc["architecture"]:
        story.append(_para(f"• {step}", body))
    story.append(PageBreak())

    for section in doc["sections"]:
        story.append(_para(f"{section['id']}. {section['title']}", h2))
        story.append(_para(section["body"], body))
        story.append(Spacer(1, 0.25 * cm))

    story.append(PageBreak())
    story.append(_para("Annexe A — Formules clés", h2))
    for item in doc["formulas"]:
        story.append(_para(f"<b>{item['name']}</b> : <font name='Courier'>{item['expr']}</font>", body))

    for table_def in doc["tables"]:
        story.append(Spacer(1, 0.35 * cm))
        story.append(_para(f"<b>{table_def['title']}</b>", h2))
        rows = [table_def["headers"]] + table_def["rows"]
        story.append(_table(rows, [5.5 * cm, 10 * cm]))

    story.append(PageBreak())
    story.append(_para("Annexe B — Limites et bonnes pratiques", h2))
    for limit in doc["limits"]:
        story.append(_para(f"• {limit}", body))

    pdf.build(story)
    return output
