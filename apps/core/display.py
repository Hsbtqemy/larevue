ISSUE_TONES: dict[str, str] = {
    "under_review": "neutral",
    "accepted": "info",
    "in_production": "active",
    "sent_to_publisher": "progress-tone",
    "published": "done",
    "refused": "refused",
}

ARTICLE_TONES: dict[str, str] = {
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
