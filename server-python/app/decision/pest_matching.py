"""Maps a farmer's free-text pest_type to the BiLSTM/ETL pest code.

Extracted from app/decision/report_signal.py so the same keyword list is
used both when a report is first submitted (app/routers/reports.py sets
pest_code at insert time) and when scoring older rows that predate the
pest_code column (see app/data/reports_store.py:backfill_pest_codes()).
Previously this lived only in report_signal.py and ran as a live substring
scan on every forecast request; it's now a one-time lookup at write time.
"""

PEST_KEYWORDS: dict[str, list[str]] = {
    "BPH": ["brown planthopper", "kayumangging hanip"],
    "RSB": ["stem borer", "aksip", "atip"],
}


def derive_pest_code(pest_type: str) -> str | None:
    """Returns "BPH", "RSB", or None if pest_type (e.g. "Others / Hindi
    Sigurado", or free text that matches neither) doesn't correspond to a
    pest the ETL table covers."""
    needle = pest_type.lower()
    for code, keywords in PEST_KEYWORDS.items():
        if any(keyword in needle for keyword in keywords):
            return code
    return None
