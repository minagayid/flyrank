from __future__ import annotations

import unicodedata
from datetime import date, datetime, timezone

from signal_desk.database import reader


def _pdf_text(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\n", " ")


def daily_report(user_id: int, report_day: date | None = None) -> bytes:
    report_day = report_day or datetime.now(timezone.utc).date()
    with reader() as connection:
        rows = connection.execute(
            """SELECT leads.id, triage_results.result_json
               FROM triage_results JOIN leads ON leads.id = triage_results.lead_id
               WHERE leads.user_id = ? AND date(triage_results.created_at) = ?
               ORDER BY triage_results.created_at DESC""",
            (user_id, report_day.isoformat()),
        ).fetchall()

    lines = [
        "Signal Desk | Daily triage snapshot",
        f"UTC date: {report_day.isoformat()}",
        f"Completed reviews: {len(rows)}",
        "Human review is required. Scores are not probabilities or decisions.",
        "",
    ]
    shown_rows = rows[:13]
    for row in shown_rows:
        import json

        result = json.loads(row["result_json"])
        lines.append(
            f"{row['id']} | fit hint {result['fit_score']}/100 | urgency {result['urgency']}"
        )
        lines.append(f"  {result['summary']}")
        lines.append(f"  Next question: {result['next_question']}")
    if not rows:
        lines.append("No triage results were completed on this date.")
    if len(rows) > len(shown_rows):
        lines.append(f"{len(rows) - len(shown_rows)} more results omitted from this one-page snapshot.")

    commands = ["BT", "/F1 15 Tf", "50 748 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("0 -14 Td")
            if index == 1:
                commands.append("/F1 10 Tf")
        commands.append(f"({_pdf_text(line[:180])}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)
