"""SVG icon paths keyed by name.

Each value is the inner SVG content (paths, circles, rects).
The {% icon %} template tag wraps these in a full <svg> element.
Common attrs on the <svg>: viewBox="0 0 24 24" fill="none" stroke="currentColor"
stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round".
"""

ICONS: dict[str, str] = {
    "home":     '<path d="M3 11L12 3l9 8"/><path d="M5 10v10h14V10"/>',
    "file":     '<path d="M14 3H6v18h12V7z"/><path d="M14 3v4h4"/>',
    "users":    '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-5.5 6.5-5.5S15.5 16.5 15.5 20"/><circle cx="17" cy="9" r="2.5"/><path d="M15 14c3 0 6 1.5 6 4.5"/>',
    "archive":  '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11h14V8"/><path d="M10 12h4"/>',
    "plus":     '<path d="M12 5v14M5 12h14"/>',
    "chevron":  '<path d="M7 10l5 5 5-5"/>',
    "chevronR": '<path d="M10 7l5 5-5 5"/>',
    "chevronU": '<path d="M7 14l5-5 5 5"/>',
    "chevronD": '<path d="M7 10l5 5 5-5"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "clock":    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "search":   '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.5-4.5"/>',
    "bell":     '<path d="M6 9a6 6 0 0112 0c0 7 3 7 3 9H3c0-2 3-2 3-9z"/><path d="M10 20a2 2 0 004 0"/>',
    "upload":   '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 20h16"/>',
    "download": '<path d="M12 4v12M17 11l-5 5-5-5"/><path d="M4 20h16"/>',
    "book":     '<path d="M4 4v15a1 1 0 001 1h15"/><path d="M8 4h12v14H8z"/>',
    "dot":      '<circle cx="12" cy="12" r="3"/>',
    "close":    '<path d="M6 6l12 12M18 6L6 18"/>',
    "mail":     '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "dots":     '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
    "edit":     '<path d="M4 20h4l10-10-4-4L4 16v4z"/>',
    "check":    '<path d="M5 13l4 4 10-10"/>',
    "back":     '<path d="M10 6l-6 6 6 6"/><path d="M4 12h16"/>',
    "info":     '<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v5h1"/>',
    "warn":     '<path d="M12 3L2 20h20L12 3z"/><path d="M12 10v4M12 17h.01"/>',
    "eye":      '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "lock":     '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>',
    "history":  '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/><path d="M3 12H1"/>',
    "grip":     '<circle cx="9" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="18" r="1"/>',
}
