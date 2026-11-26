"""Export report/report.md to styled report/report.pdf and report/report.docx."""

from __future__ import annotations

import html
import re
import subprocess
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "report" / "report.md"
PDF_PATH = ROOT / "report" / "report.pdf"
HTML_PATH = ROOT / "outputs" / "tmp_assembly" / "report_export.html"
DOCX_PATH = ROOT / "report" / "report.docx"


def md_inline_to_html(text: str) -> str:
    esc = html.escape(text)
    esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
    esc = re.sub(r"\*(.+?)\*", r"<i>\1</i>", esc)
    esc = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", esc)
    return esc


def export_pdf(lines: list[str]) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("RepTitle", parent=styles["Heading1"], fontSize=18, spaceAfter=12)
    h2_style = ParagraphStyle("RepH2", parent=styles["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=6)
    body_style = ParagraphStyle("RepBody", parent=styles["BodyText"], fontSize=10.5, leading=14, spaceAfter=6)
    bullet_style = ParagraphStyle("RepBullet", parent=body_style, leftIndent=18, firstLineIndent=-10)

    story = []
    for raw in lines:
        line = raw.rstrip()
        if not line:
            story.append(Spacer(1, 0.06 * inch))
        elif line.startswith("# "):
            story.append(Paragraph(md_inline_to_html(line[2:]), title_style))
        elif line.startswith("## "):
            story.append(Paragraph(md_inline_to_html(line[3:]), h2_style))
        elif line.startswith("---"):
            story.append(Spacer(1, 0.08 * inch))
        elif line.startswith("- ") or re.match(r"^\d+\.\s", line):
            story.append(Paragraph("• " + md_inline_to_html(re.sub(r"^(-\s|\d+\.\s)", "", line)), bullet_style))
        else:
            story.append(Paragraph(md_inline_to_html(line), body_style))

    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        title="The Heritage Short — Project Report",
    )
    doc.build(story)


def export_docx(lines: list[str]) -> None:
    """Write a clean, valid OOXML .docx archive directly via zipfile."""
    import zipfile

    paragraphs: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line or line.startswith("---"):
            continue
        style_id = "Normal"
        text = line
        if line.startswith("# "):
            style_id = "Heading1"
            text = line[2:]
        elif line.startswith("## "):
            style_id = "Heading2"
            text = line[3:]
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"`(.+?)`", r"\1", text)
        esc = html.escape(text)
        paragraphs.append(
            f'<w:p><w:pPr><w:pStyle w:val="{style_id}"/></w:pPr><w:r><w:t xml:space="preserve">{esc}</w:t></w:r></w:p>'
        )

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(paragraphs)}<w:sectPr/></w:body></w:document>'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
        '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>'
        "</w:styles>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )

    DOCX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DOCX_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/styles.xml", styles_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)


def main() -> None:
    lines = MD_PATH.read_text(encoding="utf-8").splitlines()
    export_pdf(lines)
    export_docx(lines)
    print(f"Exported {PDF_PATH.relative_to(ROOT)} ({PDF_PATH.stat().st_size} bytes)")
    print(f"Exported {DOCX_PATH.relative_to(ROOT)} ({DOCX_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
