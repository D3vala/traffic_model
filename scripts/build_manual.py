"""Build the user manual PDF from README.md using ReportLab.

Run from any directory: python scripts/build_manual.py
Requires reportlab. The README remains the single content source.
"""

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Frame, HRFlowable, Image, KeepTogether,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "MANUAL.pdf"
PAGE_W, PAGE_H = A4
MARGIN = 48
WIDTH = PAGE_W - MARGIN * 2
INK = colors.HexColor("#1E2329")
MUTED = colors.HexColor("#52514E")
PAINT = colors.HexColor("#F6C945")
BLUE = colors.HexColor("#1F5FB0")
LIGHT = colors.HexColor("#EEF0F2")
HAIRLINE = colors.HexColor("#D9DCDF")


def register_fonts():
    candidates = [
        (Path("C:/Windows/Fonts"), "arial.ttf", "arialbd.ttf", "ariali.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSans.ttf",
         "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf"),
    ]
    for directory, regular, bold, italic in candidates:
        if all((directory / filename).exists() for filename in (regular, bold, italic)):
            for name, filename in (("Manual", regular), ("Manual-Bold", bold),
                                   ("Manual-Italic", italic)):
                pdfmetrics.registerFont(TTFont(name, str(directory / filename)))
            pdfmetrics.registerFontFamily("Manual", normal="Manual", bold="Manual-Bold",
                                         italic="Manual-Italic", boldItalic="Manual-Bold")
            return "Manual", "Manual-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, BOLD = register_fonts()
STYLES = {
    "Body": ParagraphStyle("Body", fontName=FONT, fontSize=10.4, leading=15,
                           textColor=INK, spaceAfter=9, splitLongWords=True),
    "H2": ParagraphStyle("H2", fontName=BOLD, fontSize=20, leading=24,
                         textColor=INK, spaceBefore=22, spaceAfter=12, keepWithNext=True),
    "H3": ParagraphStyle("H3", fontName=BOLD, fontSize=12.2, leading=16,
                         textColor=INK, spaceBefore=13, spaceAfter=7, keepWithNext=True),
    "List": ParagraphStyle("List", fontName=FONT, fontSize=10.4, leading=15,
                           textColor=INK, leftIndent=17, firstLineIndent=-17,
                           spaceAfter=6, splitLongWords=True),
    "Table": ParagraphStyle("Table", fontName=FONT, fontSize=9.3, leading=13,
                            textColor=INK, splitLongWords=True),
    "TableHead": ParagraphStyle("TableHead", fontName=BOLD, fontSize=9.3, leading=13,
                                textColor=colors.white, splitLongWords=True),
    "Code": ParagraphStyle("Code", fontName="Courier", fontSize=8, leading=12,
                           textColor=INK, splitLongWords=True, spaceAfter=3),
    "Caption": ParagraphStyle("Caption", fontName=FONT, fontSize=9, leading=12,
                              textColor=MUTED, spaceBefore=6, spaceAfter=12),
}


def anchor(text):
    return re.sub(r"[^a-z0-9 -]", "", text.lower()).replace(" ", "-")


def inline(text):
    # Protect links and inline code while escaping normal Markdown text.
    protected = []

    def protect(value):
        protected.append(value)
        return f"MANUALTOKEN{len(protected) - 1}END"

    def link(match):
        label, target = match.groups()
        if target.startswith("#"):
            value = f'<link href="{html.escape(target, quote=True)}" color="#1F5FB0">{html.escape(label)}</link>'
        elif target.startswith(("https://", "http://")):
            value = f'<link href="{html.escape(target, quote=True)}" color="#1F5FB0">{html.escape(label)}</link>'
        else:
            value = html.escape(label)
        return protect(value)

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = re.sub(r"`([^`]+)`", lambda m: protect(
        '<font name="Courier" size="9">' + html.escape(m.group(1)) + '</font>'), text)
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    for i, value in enumerate(protected):
        text = text.replace(f"MANUALTOKEN{i}END", value)
    return text


class ManualDocument(BaseDocTemplate):
    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        if flowable.style.name not in ("H2", "H3"):
            return
        text = flowable.getPlainText()
        key = getattr(flowable, "bookmark_key", anchor(text))
        self.canv.bookmarkPage(key)
        level = 0 if flowable.style.name == "H2" else 1
        self.canv.addOutlineEntry(text, key, level=level, closed=False)
        if level == 0:
            self.notify("TOCEntry", (0, text, self.page, key))


def page_chrome(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(HAIRLINE)
    canvas.setLineWidth(0.6)
    if doc.page > 1:
        canvas.setFont(BOLD, 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, PAGE_H - 29, "MMDA TRAFFIC CRASH SIMULATOR")
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 29, "USER MANUAL")
        canvas.line(MARGIN, PAGE_H - 36, PAGE_W - MARGIN, PAGE_H - 36)
    canvas.line(MARGIN, 39, PAGE_W - MARGIN, 39)
    canvas.setFont(FONT, 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 25, "Group 9 - AM3  |  5 October 2026")
    canvas.drawRightString(PAGE_W - MARGIN, 25, str(doc.page))
    canvas.restoreState()


def table(rows):
    count = len(rows[0])
    widths = [WIDTH / count] * count
    if count == 2:
        widths = [WIDTH * 0.37, WIDTH * 0.63]
    elif count == 3:
        widths = [WIDTH * 0.23, WIDTH * 0.20, WIDTH * 0.57]
    elif count == 4:
        # The annual-result table needs more room for its range and rate.
        if rows[0][0] == "Road":
            widths = [WIDTH * 0.12, WIDTH * 0.18, WIDTH * 0.35, WIDTH * 0.35]
        else:
            widths = [WIDTH * 0.15, WIDTH * 0.43, WIDTH * 0.21, WIDTH * 0.21]
    content = [[Paragraph(inline(value), STYLES["TableHead" if i == 0 else "Table"])
                for value in row] for i, row in enumerate(rows)]
    result = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, HAIRLINE),
    ]))
    return result


def parse_body(lines):
    story = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("## ") or line.startswith("### "):
            level = "H3" if line.startswith("### ") else "H2"
            text = line.split(" ", 1)[1]
            if text.startswith("14. Maintainer reference"):
                story.append(PageBreak())
            p = Paragraph(inline(text), STYLES[level])
            p.bookmark_key = anchor(text)
            story.append(p)
            i += 1
            continue
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            blocks = [[Paragraph(html.escape(value), STYLES["Code"])] for value in code]
            box = Table(blocks, colWidths=[WIDTH], hAlign="LEFT")
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
            story.extend([box, Spacer(1, 10)])
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [part.strip() for part in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                    rows.append(cells)
                i += 1
            rendered_table = table(rows)
            story.extend([KeepTogether([rendered_table]) if len(rows) <= 6 else rendered_table,
                          Spacer(1, 12)])
            continue
        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        if image_match:
            caption, filename = image_match.groups()
            img = Image(str(ROOT / filename))
            scale = min(WIDTH / img.imageWidth, 300 / img.imageHeight)
            img.drawWidth = img.imageWidth * scale
            img.drawHeight = img.imageHeight * scale
            img.hAlign = "CENTER"
            story.append(KeepTogether([img, Paragraph(inline(caption), STYLES["Caption"])]))
            i += 1
            continue
        match = re.match(r"^(\d+)\.\s+(.*)$", line)
        if match or line.startswith("- "):
            prefix = match.group(1) + "." if match else "-"
            text = match.group(2) if match else line[2:]
            story.append(Paragraph(html.escape(prefix) + " " + inline(text), STYLES["List"]))
            i += 1
            continue
        paragraph = []
        while i < len(lines) and lines[i].strip():
            paragraph.append(inline(lines[i].strip())
                             + ("<br/>" if lines[i].endswith("  ") else " "))
            i += 1
        story.append(Paragraph("".join(paragraph).strip(), STYLES["Body"]))
    return story


def main():
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    contents_at = lines.index("## Contents")
    start_at = lines.index("## 1. Start here")
    story = []
    title = ParagraphStyle("Title", fontName=BOLD, fontSize=29, leading=32,
                           textColor=INK, spaceAfter=12)
    subtitle = ParagraphStyle("Subtitle", fontName=FONT, fontSize=19, leading=24,
                              textColor=MUTED, spaceAfter=20)
    story.extend([
        Paragraph("MMDA Traffic<br/>Crash Simulator", title),
        Paragraph("User manual - EDSA and C5", subtitle),
        HRFlowable(width=WIDTH, thickness=4, color=PAINT, spaceAfter=14),
    ])
    story.extend(parse_body(lines[1:contents_at]))
    contents_style = ParagraphStyle("ContentsTitle", fontName=BOLD, fontSize=17,
                                    leading=22, textColor=INK, spaceBefore=16, spaceAfter=10)
    story.append(Paragraph("Contents", contents_style))
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("TOC", fontName=FONT, fontSize=9.7,
                                      leading=13, spaceBefore=1, textColor=INK,
                                      leftIndent=0, firstLineIndent=0)]
    toc.dotsMinLevel = 0
    story.extend([toc, PageBreak()])
    story.extend(parse_body(lines[start_at:]))
    doc = ManualDocument(str(OUTPUT), pagesize=A4, leftMargin=MARGIN,
                         rightMargin=MARGIN, topMargin=52, bottomMargin=54,
                         title="MMDA Traffic Crash Simulator - User Manual",
                         author="Group 9 - AM3", subject="Website operation and interpretation guide")
    frame = Frame(MARGIN, 54, WIDTH, PAGE_H - 106, leftPadding=0,
                  rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="Manual", frames=[frame], onPage=page_chrome))
    doc.multiBuild(story)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
