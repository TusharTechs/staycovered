"""Pre-fill Nebraska's real Individual Declaration Form (MLTC-118, 5/2026) from a case worksheet.

Rules:
- Only answer what the client's documents or the navigator's intake show. Unknown questions stay blank; nothing is
  guessed as "No".
- Never fill SSN, date of birth, signatures or dates: the client completes and signs those.
- Every filled field carries a reason pointing at its evidence, shown to the navigator before printing.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

from . import config
from .engine.compute import Worksheet
from .engine.model import Kind
from .store import CaseRecord

FORM = config.ROOT / "data" / "forms" / "mltc118.pdf"
FORM_ID = "MLTC-118 5/2026 (Nebraska DHHS Individual Declaration Form)"


@dataclass
class FilledField:
    field: str
    label: str
    value: str
    reason: str


def plan(rec: CaseRecord, ws: Worksheet) -> list[FilledField]:
    c = rec.case
    client = next(m for m in c.household if m.id == c.client_id)
    docs = {d.id: d.name for d in rec.documents}
    out: list[FilledField] = []
    parts = client.name.split()
    first, last = parts[0], " ".join(parts[1:]) or ""
    out += [FilledField("First Name", "First name", first, "Client record"),
            FilledField("Last Name", "Last name", last, "Client record"),
            FilledField("Name", "Who is this form being filled out for", client.name, "Client record")]

    months = set(ws.months)

    def rows(kinds: set[Kind]):
        return [e for e in c.ledger if e.kind in kinds and e.member_id == client.id
                and any(e.period_start.strftime("%Y-%m") <= m <= e.period_end.strftime("%Y-%m") for m in months)]

    def evidence(es) -> str:
        return "; ".join(sorted({f"{docs.get(e.source.doc_id, e.source.doc_id)}: \"{e.source.span}\"" for e in es if e.source}))[:300]

    vol = rows({Kind.COMMUNITY_SERVICE_HOURS})
    if vol:
        hours = sum(r.contributions and sum(x.amount for x in r.contributions if x.kind == Kind.COMMUNITY_SERVICE_HOURS.value) or 0
                    for r in ws.results)
        out += [FilledField("Yes1", "Volunteered in a qualifying month", "Yes", evidence(vol)),
                FilledField("Number of volunteer hours per month", "Volunteer hours per month", f"{hours:g}", evidence(vol)),
                FilledField("Name of Organizations", "Organization(s)", ", ".join(sorted({e.payer for e in vol if e.payer})), evidence(vol))]
    wp = rows({Kind.WORK_PROGRAM_HOURS})
    if wp:
        out += [FilledField("Yes2", "Work program in a qualifying month", "Yes", evidence(wp)),
                FilledField("Number of hours per month", "Work program hours per month",
                            f"{sum(e.amount for e in wp):g}", evidence(wp)),
                FilledField("Name of the Work Programs", "Work program(s)", ", ".join(sorted({e.payer for e in wp if e.payer})), evidence(wp))]
    edu = rows({Kind.EDUCATION_HOURS})
    if edu:
        out += [FilledField("Yes3", "Enrolled in school in a qualifying month", "Yes", evidence(edu)),
                FilledField("Name of school or program", "School or program", ", ".join(sorted({e.payer for e in edu if e.payer})), evidence(edu))]
    if client.caretaker_of_young_child:
        out.append(FilledField("Yes4", "Parent/caretaker of a child 13 or younger", "Yes", "Navigator intake (client statement)"))
    if client.caretaker_of_disabled_person:
        out.append(FilledField("Yes7", "Caring for a person with a disability", "Yes", "Navigator intake (client statement)"))
    if client.recently_incarcerated:
        out.append(FilledField("Incarcerated 12 mo Yes", "Incarcerated in the last 12 months", "Yes", "Navigator intake"))
    if client.medically_frail_indicators:
        out += [FilledField("serious or complex medical condition  Yes", "Medically frail / special medical needs", "Yes",
                            "Navigator intake: " + ", ".join(client.medically_frail_indicators)),
                FilledField("Describe the health conditions the individual has that fit the list above 1", "Health conditions",
                            "; ".join(client.medically_frail_indicators)[:120], "Navigator intake")]
    if client.in_sud_treatment:
        out.append(FilledField("Yes11", "In SUD treatment in a qualifying month", "Yes", "Navigator intake"))
    if client.veteran_total_disability:
        out.append(FilledField("Yes13", "Veteran with 100% VA disability rating", "Yes", "Navigator intake"))
    out.append(FilledField("I Additional comments", "Additional comments",
                           f"Draft pre-filled with StayCovered from documents the client provided (months reviewed: "
                           f"{', '.join(ws.months)}). Client must review every answer, then sign and date.",
                           "Transparency note"))
    return out


def fill(rec: CaseRecord, ws: Worksheet) -> tuple[bytes, list[FilledField]]:
    fields = plan(rec, ws)
    reader = PdfReader(FORM)
    writer = PdfWriter()
    writer.append(reader)
    text_vals = {f.field: f.value for f in fields if f.value != "Yes" or not _is_checkbox(reader, f.field)}
    checks = {f.field for f in fields if f.value == "Yes" and _is_checkbox(reader, f.field)}
    for page in writer.pages:
        writer.update_page_form_field_values(page, text_vals, auto_regenerate=False)
        for a in page.get("/Annots") or []:
            a = a.get_object()
            name = a.get("/T") or (a.get("/Parent").get_object().get("/T") if a.get("/Parent") else None)
            if name in checks:
                a[NameObject("/V")] = NameObject("/On")
                a[NameObject("/AS")] = NameObject("/On")
    writer.set_need_appearances_writer(True)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue(), fields


def _is_checkbox(reader: PdfReader, name: str) -> bool:
    f = (reader.get_fields() or {}).get(name)
    return bool(f and f.get("/FT") == "/Btn")
