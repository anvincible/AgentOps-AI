"""Universal Design System and Typography for AgentOps AI Reporting.
Defines the executive color palette, font hierarchies, and TrueType font registration
for full Unicode support (including native Indian Rupee ₹ U+20B9 rendering).
"""

from __future__ import annotations

import os
from typing import Dict, Tuple

from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Universal Executive Palette
PALETTE = {
    "midnight_navy": "#081426",
    "deep_graphite": "#141C2B",
    "dark_card": "#0D1527",
    "card_alt": "#111B30",
    "border_metallic": "#24324D",
    "border_light": "#CBD5E1",
    "electric_cyan": "#00CFE8",
    "royal_blue": "#397BFF",
    "emerald": "#18B889",
    "violet": "#9476E8",
    "rose_pink": "#E85D9E",
    "champagne_gold": "#D6B36A",
    "warm_white": "#F7F8FA",
    "pure_white": "#FFFFFF",
    "text_dark": "#0F172A",
    "text_body": "#1E293B",
    "text_muted": "#64748B",
    "text_light": "#E2E8F0",
    "accent_risk": "#DC2626",
}

# ReportLab Color Objects
RL_COLORS = {k: colors.HexColor(v) for k, v in PALETTE.items()}

# Font Registration State
_FONTS_REGISTERED = False
_PRIMARY_FONT_NAME = "Helvetica"
_BOLD_FONT_NAME = "Helvetica-Bold"
_ITALIC_FONT_NAME = "Helvetica-Oblique"


def register_unicode_fonts() -> Tuple[str, str, str]:
    """Register TrueType Unicode fonts in ReportLab to support ₹ and clean typography.
    Returns (primary_font_name, bold_font_name, italic_font_name).
    """
    global _FONTS_REGISTERED, _PRIMARY_FONT_NAME, _BOLD_FONT_NAME, _ITALIC_FONT_NAME

    if _FONTS_REGISTERED:
        return _PRIMARY_FONT_NAME, _BOLD_FONT_NAME, _ITALIC_FONT_NAME

    # Candidate fonts in priority order
    candidate_paths = [
        # Windows Segoe UI (Native, clean, full ₹ U+20B9 glyph support)
        (
            "SegoeUI",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/segoeuii.ttf",
        ),
        # Windows Arial
        (
            "Arial",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/ariali.ttf",
        ),
        # Windows Nirmala UI (Official Indic UI font)
        (
            "NirmalaUI",
            "C:/Windows/Fonts/Nirmala.ttf",
            "C:/Windows/Fonts/NirmalaB.ttf",
            "C:/Windows/Fonts/Nirmala.ttf",
        ),
    ]

    for font_name, regular_path, bold_path, italic_path in candidate_paths:
        if os.path.exists(regular_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, regular_path))
                b_name = f"{font_name}-Bold"
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(b_name, bold_path))
                else:
                    b_name = font_name

                i_name = f"{font_name}-Italic"
                if os.path.exists(italic_path):
                    pdfmetrics.registerFont(TTFont(i_name, italic_path))
                else:
                    i_name = font_name

                _PRIMARY_FONT_NAME = font_name
                _BOLD_FONT_NAME = b_name
                _ITALIC_FONT_NAME = i_name
                _FONTS_REGISTERED = True
                return _PRIMARY_FONT_NAME, _BOLD_FONT_NAME, _ITALIC_FONT_NAME
            except Exception:
                continue

    # Fallback to standard Helvetica if TTF registration fails
    _PRIMARY_FONT_NAME = "Helvetica"
    _BOLD_FONT_NAME = "Helvetica-Bold"
    _ITALIC_FONT_NAME = "Helvetica-Oblique"
    _FONTS_REGISTERED = True
    return _PRIMARY_FONT_NAME, _BOLD_FONT_NAME, _ITALIC_FONT_NAME


def format_inr(val: Any) -> str:
    """Format numeric values as Indian Rupee string (₹ XX,XX,XXX.XX).
    Correctly formats Lakhs and Crores with Indian grouping.
    """
    if val is None:
        return "₹0.00"
    try:
        f = float(val)
        is_neg = f < 0
        f = abs(f)
        parts = f"{f:.2f}".split(".")
        int_part = parts[0]
        dec_part = parts[1]

        if len(int_part) <= 3:
            res = int_part
        else:
            last_3 = int_part[-3:]
            rest = int_part[:-3]
            groups = []
            while len(rest) > 2:
                groups.append(rest[-2:])
                rest = rest[:-2]
            if rest:
                groups.append(rest)
            groups.reverse()
            res = ",".join(groups) + "," + last_3

        return f"{'-' if is_neg else ''}₹{res}.{dec_part}"
    except (ValueError, TypeError):
        return f"₹{val}"


def format_indian_num(val: Any) -> str:
    """Format integers according to Indian numbering grouping (1,00,000)."""
    if val is None:
        return "0"
    try:
        n = int(val)
        is_neg = n < 0
        n = abs(n)
        s = str(n)
        if len(s) <= 3:
            res = s
        else:
            last_3 = s[-3:]
            rest = s[:-3]
            groups = []
            while len(rest) > 2:
                groups.append(rest[-2:])
                rest = rest[:-2]
            if rest:
                groups.append(rest)
            groups.reverse()
            res = ",".join(groups) + "," + last_3
        return f"{'-' if is_neg else ''}{res}"
    except (ValueError, TypeError):
        return str(val)
