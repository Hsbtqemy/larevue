MONTH_SHORT: list[str] = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]
MONTH_ABBR: list[str] = [m.rstrip(".") for m in MONTH_SHORT]

ISSUE_TONES: dict[str, str] = {
    "under_review": "neutral",
    "accepted": "info",
    "in_review": "active",
    "in_revision": "active",
    "final_check": "progress-tone",
    "sent_to_publisher": "progress-tone",
    "published": "done",
    "refused": "refused",
}

ARTICLE_TONES: dict[str, str] = {
    "pending": "neutral",
    "received": "neutral",
    "in_review": "active",
    "reviews_received": "info",
    "in_author_revision": "progress-tone",
    "revised": "info",
    "validated": "done",
}

VERDICT_TONES: dict[str, str] = {
    "favorable": "done",
    "needs_revision": "progress-tone",
    "unfavorable": "refused",
}

VERDICT_LABELS: dict[str, str] = {
    "favorable": "Favorable",
    "needs_revision": "Révision requise",
    "unfavorable": "Défavorable",
}

DEADLINE_LABELS: dict[str, str] = {
    "deadline_articles": "Limite articles",
    "deadline_reviews": "Limite relectures",
    "deadline_v2": "Limite V2",
    "deadline_final_check": "Limite vérif. finale",
    "deadline_sent_to_publisher": "Limite envoi éditeur",
    "planned_publication_date": "Parution prévue",
}

DEADLINE_TYPES: dict[str, str] = {
    "deadline_articles": "articles",
    "deadline_reviews": "reviews",
    "deadline_v2": "v2",
    "deadline_final_check": "final_check",
    "deadline_sent_to_publisher": "publisher",
    "planned_publication_date": "publication",
}
