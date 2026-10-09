"""Ready-to-file packet PDF: cover sheet, month-by-month worksheet with evidence index, flags, open items."""

from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import rules
from .engine.compute import Worksheet
from .store import CaseRecord

STATUS = {"meets": "Meets requirement", "does_not_meet": "Does not meet yet", "insufficient_evidence": "No evidence yet"}
PATH = {"hours": "80+ activity hours", "household_income": "household income at or above threshold",
        "combined": "activity hours + income converted to hours", "seasonal_average": "6-month seasonal income average"}


def build_packet(rec: CaseRecord, ws: Worksheet) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.7 * inch, rightMargin=0.7 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            title=f"StayCovered packet — {rec.client_name}")
    ss = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=ss["BodyText"], fontSize=8.5, leading=11)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=10, leading=13)
    h = ss["Heading2"]
    story = []

    story += [Paragraph("Medicaid work requirement — documentation packet", ss["Title"]),
              Paragraph(f"Client: <b>{rec.client_name}</b> &nbsp; Case: {rec.case.id} &nbsp; State: {ws.jurisdiction}", body),
              Paragraph(f"Prepared {date.today().isoformat()} using rules in force on {ws.as_of.isoformat()}.", body)]
    if rec.synthetic:
        story.append(Paragraph("<b>SYNTHETIC DEMO DATA — not a real person.</b>", body))
    if ws.cure_deadline:
        story.append(Paragraph(f"<b>Respond by: {ws.cure_deadline.isoformat()}</b> (notice dated {rec.case.notice_date}).", body))
    story.append(Spacer(1, 8))
    story.append(Paragraph("This packet organises the client's own documents against the published rules. "
                           "It is not an eligibility decision. The state agency decides.", small))

    story.append(Paragraph("Summary by month", h))
    rows = [["Month", "Result", "How", "Activity hrs", "Household income", "Combined hrs"]]
    for r in ws.results:
        rows.append([r.month, STATUS[r.status], PATH.get(r.path or "", "—"), f"{r.activity_hours:g}",
                     f"${r.household_income:,.2f} (need ${r.income_threshold:,.0f})", f"{r.combined_hours:g}"])
    t = Table(rows, repeatRows=1, colWidths=[0.7 * inch, 1.3 * inch, 1.7 * inch, 0.8 * inch, 1.6 * inch, 0.8 * inch])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)

    story.append(Paragraph("Evidence index", h))
    docs = {d.id: d.name for d in rec.documents}
    erows = [["Month", "Row", "Type", "Counted", "From document", "Exact text"]]
    for r in ws.results:
        for c in r.contributions:
            erows.append([r.month, c.entry_id, c.kind.replace("_", " "), f"{c.amount:g}" + (f" ({c.share:.0%})" if c.share < 1 else ""),
                          Paragraph(docs.get(c.doc_id or "", c.doc_id or "—"), small), Paragraph(c.span[:180], small)])
    et = Table(erows, repeatRows=1, colWidths=[0.6 * inch, 0.9 * inch, 1.1 * inch, 0.8 * inch, 1.4 * inch, 2.1 * inch])
    et.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
                            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(et)

    amb = sorted({a for r in ws.results for a in r.ambiguities})
    if amb or ws.warnings:
        story.append(Paragraph("Things to confirm with the agency", h))
        for a in amb + ws.warnings:
            story.append(Paragraph("• " + a, small))

    if ws.exemptions:
        story.append(Paragraph("Possible exemptions to raise (not decided)", h))
        for e in ws.exemptions:
            story.append(Paragraph(f"• <b>{e.label}</b> — {e.action}", small))

    story.append(PageBreak())
    story.append(Paragraph("Rules used (with official sources)", h))
    used = sorted({f for r in ws.results for f in r.facts_used} | {fid for e in ws.exemptions for fid in e.fact_ids})
    for fid in used:
        f = rules.fact(fid, ws.as_of)
        if not f:
            continue
        story.append(Paragraph(f"<b>{f.id}</b>: {f.statement}", small))
        for c in f.citations[:1]:
            story.append(Paragraph(f'&nbsp;&nbsp;"{c.quote[:300]}" — {c.source_id}', small))
    unver = [v for v in ws.params.values() if not v["verified"]]
    if unver:
        story.append(Paragraph("Defaults without captured rule text: " + "; ".join(f"{v['label']} = {v['value']}" for v in unver), small))
    doc.build(story)
    return buf.getvalue()
