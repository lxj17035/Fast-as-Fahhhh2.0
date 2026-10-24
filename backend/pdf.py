import base64
import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .errors import AppError
from .quotations import expected_version

FONT_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("QuoteText", str(FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("QuoteBold", str(FONT_DIR / "VeraBd.ttf")))
pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def paragraph(value, *, size=10, bold=False, right=False, color="#17283b"):
    value = str(value)
    cjk = any(ord(character) >= 0x2E80 for character in value)
    style = ParagraphStyle("quote", fontName="QuoteBold" if bold else "QuoteText",
                           fontSize=size, leading=size * 1.45, textColor=colors.HexColor(color),
                           alignment=TA_RIGHT if right else 0, wordWrap="CJK" if cjk else None,
                           spaceAfter=5)
    runs = re.split(r"([\u2E80-\u9FFF]+)", value)
    markup = "".join('<font name="STSong-Light">' + escape(run) + '</font>'
                     if run and 0x2E80 <= ord(run[0]) <= 0x9FFF else escape(run) for run in runs)
    return Paragraph(markup.replace("\n", "<br/>"), style)


def render_pdf(quote):
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=42, leftMargin=42,
                                 topMargin=40, bottomMargin=48, title=quote["number"],
                                 author=quote["company"]["companyName"])
    width = A4[0] - 84
    incomplete = bool(quote["missingInformation"] or quote["total"] is None
                      or not quote["client"]["name"].strip() or not quote["items"]
                      or any(not item["description"].strip() for item in quote["items"]))
    story = [paragraph(quote["company"]["companyName"], size=19, bold=True),
             paragraph(quote["company"]["companyAddress"]), Spacer(1, 12),
             paragraph("DRAFT QUOTATION" if incomplete else "QUOTATION", size=22, bold=True),
             paragraph(f'{quote["number"]}  |  Saved version {quote["version"]}', size=9), Spacer(1, 10)]
    if quote.get("parentQuotationNumber"):
        story.append(paragraph(quote["relationship"].capitalize() + " of " + quote["parentQuotationNumber"], size=9))
    metadata = Table([
        [paragraph("PREPARED FOR", bold=True, size=9), paragraph("DATES AND CURRENCY", bold=True, size=9)],
        [paragraph(quote["client"]["name"] or "Client name required"),
         paragraph(f'Issue date: {quote["issueDate"]}\nValid through: {quote["expiryDate"]}\nCurrency: {quote["currency"]}')],
        [paragraph(quote["client"]["address"] or "Address not provided"),
         paragraph("Validity uses the issue date (Asia/Kuala_Lumpur).", size=8)],
    ], colWidths=[width * .52, width * .48])
    metadata.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    story.extend([metadata, Spacer(1, 18)])
    rows = [[paragraph("Description", bold=True, color="#ffffff"),
             paragraph("Qty", bold=True, right=True, color="#ffffff"),
             paragraph("Unit price", bold=True, right=True, color="#ffffff"),
             paragraph("Amount", bold=True, right=True, color="#ffffff")]]
    for item in quote["items"]:
        item_content = [paragraph(item.get("item_name", item["description"]) or "Description required"),
                        paragraph("Unit: " + item.get("unit", "unit"), size=8, color="#64748b")]
        if item.get("notes"):
            item_content.append(paragraph(item["notes"], size=9))
        rows.append([item_content,
                     paragraph(item["quantity"] if item["quantity"] is not None else "TBD", right=True),
                     paragraph(item["unitPrice"] if item["unitPrice"] is not None else "TBD", right=True),
                     paragraph(item["lineTotal"] if item["lineTotal"] is not None else "TBD", right=True)])
    if len(rows) == 1:
        rows.append([paragraph("Items pending PM review"), paragraph("TBD"), paragraph("TBD"), paragraph("TBD")])
    rows.append([paragraph(f'TOTAL ({quote["currency"]})', size=12, bold=True), "", "",
                 paragraph(quote["total"] if quote["total"] is not None else "Pending pricing",
                           size=12, bold=True, right=True)])
    total_row = len(rows) - 1
    notes_in_table = bool(quote["notes"]) and len(quote["notes"]) <= 1000
    if notes_in_table:
        rows.append([paragraph("NOTES\n" + quote["notes"]), "", "", ""])
    oversized_rows = any(len(item["description"]) + len(item.get("notes", "")) > 1000 for item in quote["items"])
    table = LongTable(rows, colWidths=[width * .49, width * .12, width * .19, width * .20],
                      repeatRows=1, splitInRow=int(oversized_rows), hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#203e57")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f1f5f8"), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, 0), .5, colors.HexColor("#203e57")),
        ("SPAN", (0, total_row), (2, total_row)),
        ("BACKGROUND", (0, total_row), (-1, total_row), colors.HexColor("#e3edf3")),
    ]))
    if notes_in_table:
        table.setStyle(TableStyle([("SPAN", (0, -1), (-1, -1)),
                                   ("BACKGROUND", (0, -1), (-1, -1), colors.white)]))
    # Keep ordinary last items with their total; very long rows must remain
    # splittable so they can flow across pages instead of raising LayoutError.
    last_length = (len(quote["items"][-1]["description"]) + len(quote["items"][-1].get("notes", ""))) if quote["items"] else 0
    if last_length + (len(quote["notes"]) / 2 if notes_in_table else 0) <= 1000:
        table.setStyle(TableStyle([("NOSPLIT", (0, -3 if notes_in_table else -2), (-1, -1))]))
    elif notes_in_table:
        table.setStyle(TableStyle([("NOSPLIT", (0, -2), (-1, -1))]))
    story.extend([table, Spacer(1, 12)])
    if incomplete:
        story.extend([Spacer(1, 10), paragraph("INCOMPLETE DRAFT - PM review required", bold=True, color="#9b4c10")])
    if quote["notes"] and not notes_in_table:
        story.extend([Spacer(1, 15), paragraph("NOTES", bold=True, size=9), paragraph(quote["notes"])])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("QuoteText", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(42, 26, "Synthetic-data demo | " + quote["number"])
        canvas.drawRightString(A4[0] - 42, 26, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


class PDFService:
    def __init__(self, store, quotations):
        self.store, self.quotations = store, quotations

    def get(self, quotation_id, version=None):
        with self.store.transaction():
            quote = self.quotations.get(quotation_id)
            if version is not None:
                expected_version(quote, version)
            delivered = quote["status"] == "send_failed" and self.quotations.delivered_pdf(quotation_id)
            if quote["status"] in {"draft", "send_failed"} and not delivered and not self.quotations.source_is_current(quote):
                raise AppError("Review the latest customer messages before refreshing a quotation PDF", 409)
            key = f'{quotation_id}:{quote["version"]}'
            try:
                cached = self.store.get("pdfs", key)
            except AppError as error:
                if error.status != 404:
                    raise
                cached = {"data": base64.b64encode(render_pdf(quote)).decode("ascii")}
                self.store.put("pdfs", key, cached)
            return base64.b64decode(cached["data"]), quote["version"]
