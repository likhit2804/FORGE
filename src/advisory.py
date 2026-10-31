"""Constrained, source-backed advisory generation for the MVP.

This is intentionally template-based. An LLM may improve phrasing later, but
it must receive only this structured output and cannot invent figures.
"""

from __future__ import annotations


def build_advisory(ranking: list[dict], retrieval: dict, language: str = "en",
                   confidence_label: str | None = None,
                   reservoir_context: dict | None = None) -> dict:
    if not ranking:
        raise ValueError("cannot generate an advisory without a district ranking")
    top = ranking[:3]
    top_names = [row["district"] for row in top]
    analogue_sources = [item["event"].source for item in retrieval["analogues"][:3]]
    district_sources = {}
    for row in top:
        local = retrieval.get("district_analogues", {}).get(row["district"], {})
        sources = [item["event"].source for item in local.get("analogues", [])[:3]]
        district_sources[row["district"]] = sources or analogue_sources
    confidence = confidence_label or ("Low" if retrieval["abstained"] or retrieval["out_of_range"] else "Medium")
    reservoir_note_en = ""
    reservoir_note_ta = ""
    if reservoir_context is not None:
        flagged = sum(row.get("buffer_concern") is True for row in reservoir_context.get("records", []))
        threshold = reservoir_context.get("buffer_concern_threshold_pct", 80)
        report_date = reservoir_context.get("data_date", "unknown date")
        reservoir_note_en = (f" AGRISNET context ({report_date}) flags {flagged} reservoir(s) at or above the "
                             f"user-selected {threshold:.0f}% storage heuristic; it is not district-linked and "
                             "does not affect the ranking.")
        reservoir_note_ta = (f" AGRISNET நீர்த்தேக்கச் சூழல் ({report_date}): பயனர் தேர்ந்தெடுத்த "
                             f"{threshold:.0f}% சேமிப்பு அளவுகோலை {flagged} நீர்த்தேக்கங்கள் எட்டியுள்ளன; "
                             "இது மாவட்ட முன்னுரிமையுடன் இணைக்கப்படவில்லை, மதிப்பீட்டையும் மாற்றாது.")
    if language == "ta":
        text = (f"முன்னுரிமை மாவட்டங்கள்: {', '.join(top_names)}. "
                f"இது வரலாற்று ஒப்புமை மற்றும் மழை அபாய மதிப்பீட்டை அடிப்படையாகக் கொண்ட தயார்நிலை அறிவுரை. "
                f"அதிகாரப்பூர்வ IMD மற்றும் மாவட்ட நிர்வாக எச்சரிக்கைகளுக்கு முன்னுரிமை அளிக்கவும்."
                f"{reservoir_note_ta}")
    else:
        text = (f"Priority preparation districts: {', '.join(top_names)}. "
                "This is a preparedness advisory based on historical analogues and rainfall-risk scoring. "
                "Official IMD and district-administration warnings take precedence."
                f"{reservoir_note_en}")
    return {
        "language": language,
        "text": text,
        "confidence": confidence,
        "source_tags": {
            "analogue_events": analogue_sources,
            "analogue_events_by_district": district_sources,
            "ranking": "application hazard/exposure/vulnerability/isolation calculation",
            "official_precedence": "https://api.imd.gov.in/public/api_reference.html",
            "reservoir_context": (reservoir_context.get("source_url") if reservoir_context else None),
        },
    }
