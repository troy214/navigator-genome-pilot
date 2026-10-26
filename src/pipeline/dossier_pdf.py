"""Render the evidence dossier to a physician-facing PDF (reportlab).

Research use only. Every page footer carries the research-use notice.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable)

RESEARCH_NOTICE = (
    "RESEARCH USE ONLY. Navigator Genome Pilot is a research support tool. It is NOT a "
    "diagnostic system and does NOT provide medical advice. All findings are hypotheses with "
    "explicit uncertainty labels and must be independently verified by a qualified professional."
)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawString(0.75 * inch, 0.5 * inch, RESEARCH_NOTICE[:120])
    canvas.drawString(0.75 * inch, 0.38 * inch, RESEARCH_NOTICE[120:])
    canvas.drawRightString(7.75 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def render_dossier(dossier: dict, out_path: str | Path) -> str:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                            topMargin=0.8 * inch, bottomMargin=0.9 * inch)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8, textColor=colors.grey)

    el = []
    el.append(Paragraph("Navigator Genome Pilot — Evidence Dossier", h1))
    el.append(Paragraph(f"Case: {dossier.get('case_id','?')} &nbsp;|&nbsp; "
                        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
                        f"&nbsp;|&nbsp; Provider: {dossier.get('provider','?')}", small))
    el.append(Spacer(1, 4))
    el.append(Paragraph("<b>Research use only — not a diagnostic system and not medical advice.</b> "
                        "Findings below are hypotheses with explicit uncertainty labels.", small))
    el.append(HRFlowable(width="100%", color=colors.lightgrey, spaceBefore=6, spaceAfter=6))

    # Clinical summary
    if dossier.get("clinical_summary"):
        el.append(Paragraph("Clinical summary (as provided)", h2))
        el.append(Paragraph(dossier["clinical_summary"], body))

    # Phenotype terms
    if dossier.get("hpo_terms"):
        el.append(Paragraph("Mapped phenotype terms (HPO)", h2))
        el.append(Paragraph(", ".join(f"{t.get('id')} {t.get('name')}"
                                      for t in dossier["hpo_terms"]), body))

    # Ranked findings
    el.append(Paragraph("Candidate findings (ranked hypotheses)", h2))
    findings = dossier.get("findings", [])
    if not findings:
        el.append(Paragraph("No candidate findings could be assembled from available evidence.", body))
    for f in findings:
        el.append(Paragraph(
            f"<b>#{f['rank']}. {f.get('gene') or 'unknown gene'} "
            f"{('— ' + f['variant']) if f.get('variant') else ''}</b> "
            f"&nbsp;[confidence: {f.get('confidence','uncertain')}]", body))
        if f.get("rationale"):
            el.append(Paragraph(f"<i>Rationale:</i> {f['rationale']}", body))
        if f.get("supporting"):
            el.append(Paragraph("<i>Supporting evidence:</i>", body))
            for s in f["supporting"][:6]:
                el.append(Paragraph(f"• {s}", body))
        if f.get("contradicting"):
            el.append(Paragraph("<i>Contradicting / cautionary:</i>", body))
            for s in f["contradicting"][:6]:
                el.append(Paragraph(f"• {s}", body))
        el.append(Paragraph(f"<i>Uncertainty:</i> {f.get('uncertainty','') or 'see labels above'}", small))
        el.append(Spacer(1, 6))

    # Red-team summary
    if dossier.get("red_team"):
        el.append(Paragraph("Independent red-team review", h2))
        for c in dossier["red_team"][:8]:
            el.append(Paragraph(f"• {c}", body))

    # Sources unavailable (say when it doesn't know)
    if dossier.get("sources_unavailable"):
        el.append(Paragraph("Sources unavailable at run time", h2))
        el.append(Paragraph(
            "The following sources could not be reached; absence of evidence here is NOT "
            "evidence of absence: " + ", ".join(dossier["sources_unavailable"]), small))

    # Full evidence ledger table
    el.append(Paragraph("Evidence ledger", h2))
    rows = [["Claim", "Source", "Conf.", "Knowledge"]]
    for e in dossier.get("evidence", [])[:60]:
        rows.append([
            Paragraph(e.get("claim", "")[:220], small),
            Paragraph(str(e.get("source", ""))[:60], small),
            e.get("confidence", ""), e.get("knowledge", "")])
    tbl = Table(rows, colWidths=[3.4 * inch, 1.9 * inch, 0.6 * inch, 0.8 * inch], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b2029")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
    ]))
    el.append(tbl)

    doc.build(el, onFirstPage=_footer, onLaterPages=_footer)
    return str(out_path)
