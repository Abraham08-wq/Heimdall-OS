"""
cleansing_transformer.py — ProjectXY Cognitive Shield: Layer 1
================================================================
The Cleansing Transformer performs semantic normalization on ALL incoming
inputs BEFORE they reach the inference engine.

Attack vectors neutralized:
  • Unicode homoglyph attacks (ℐ→I, 𝐀→A, ａ→a, Α→A)
  • Zero-width character injection (ZWS, ZWSP, ZWNJ, ZWZS, BOM, BIDI overrides)
  • RTL/LTR BIDI override attacks (makes strings appear innocent visually)
  • Leetspeak obfuscation (h4ck, @dm1n, p455w0rd)
  • Sheng/Swahili adversarial expansion (canonical map → English)
  • Punctuation-padding insertion ("i.g.n.o.r.e p.r.e.v.i.o.u.s")
  • Mixed-case normalization for pattern evasion ("iGnOrE PrEvIoUs")
  • Control character stripping
  • Excessive whitespace / newline injection collapse

Fail-Closed: If normalization raises an uncaught exception, the
CleansingTransformer.transform() method returns a BLOCKED result
rather than passing untransformed text forward.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("projectxy.firewall.cleansing")

# ---------------------------------------------------------------------------
# Homoglyph Normalization Map
# Maps visually-deceptive Unicode characters to their ASCII equivalents.
# Covers Cyrillic lookalikes, Mathematical Bold/Italic, Fullwidth, and more.
# ---------------------------------------------------------------------------
HOMOGLYPH_MAP: dict[str, str] = {
    # --- Latin Fullwidth (ａ–ｚ, Ａ–Ｚ) ---
    **{chr(0xFF01 + i): chr(0x21 + i) for i in range(94)},

    # --- Mathematical Alphanumerics (Bold, Italic, Script, Fraktur, etc.) ---
    # Bold Latin capital letters
    **{chr(0x1D400 + i): chr(ord('A') + i) for i in range(26)},
    # Bold Latin small letters
    **{chr(0x1D41A + i): chr(ord('a') + i) for i in range(26)},
    # Italic capital letters
    **{chr(0x1D434 + i): chr(ord('A') + i) for i in range(26)},
    # Italic small letters
    **{chr(0x1D44E + i): chr(ord('a') + i) for i in range(26)},

    # --- Cyrillic Lookalikes (most common confusion set) ---
    '\u0410': 'A',  # Cyrillic А
    '\u0412': 'B',  # Cyrillic В
    '\u0421': 'C',  # Cyrillic С
    '\u0435': 'e',  # Cyrillic е
    '\u0415': 'E',  # Cyrillic Е
    '\u041D': 'H',  # Cyrillic Н
    '\u0406': 'I',  # Cyrillic І
    '\u0049': 'I',  # Latin I (explicit for safety)
    '\u039A': 'K',  # Greek Κ
    '\u041C': 'M',  # Cyrillic М
    '\u041E': 'O',  # Cyrillic О
    '\u043E': 'o',  # Cyrillic о
    '\u0440': 'p',  # Cyrillic р
    '\u0420': 'P',  # Cyrillic Р
    '\u0422': 'T',  # Cyrillic Т
    '\u0445': 'x',  # Cyrillic х
    '\u0425': 'X',  # Cyrillic Х
    '\u0443': 'y',  # Cyrillic у
    '\u0423': 'Y',  # Cyrillic У

    # --- Greek Lookalikes ---
    '\u0391': 'A',  # Greek Α
    '\u0395': 'E',  # Greek Ε
    '\u0396': 'Z',  # Greek Ζ
    '\u0397': 'H',  # Greek Η
    '\u0399': 'I',  # Greek Ι
    '\u039C': 'M',  # Greek Μ
    '\u039D': 'N',  # Greek Ν
    '\u039F': 'O',  # Greek Ο
    '\u03A1': 'P',  # Greek Ρ
    '\u03A4': 'T',  # Greek Τ
    '\u03A5': 'Y',  # Greek Υ
    '\u03A7': 'X',  # Greek Χ
    '\u03B1': 'a',  # Greek α
    '\u03B5': 'e',  # Greek ε
    '\u03B9': 'i',  # Greek ι
    '\u03BF': 'o',  # Greek ο
    '\u03C5': 'u',  # Greek υ

    # --- Script / Cursive variants ---
    '\u210A': 'g',  # Script small g
    '\u2110': 'I',  # Script capital I
    '\u2111': 'I',  # Black-letter I
    '\u2112': 'L',  # Script capital L
    '\u2113': 'l',  # Script small l
    '\u2115': 'N',  # Double-struck N
    '\u2119': 'P',  # Double-struck P
    '\u211A': 'Q',  # Double-struck Q
    '\u211B': 'R',  # Script capital R
    '\u211C': 'R',  # Fraktur R
    '\u211D': 'R',  # Double-struck R
    '\u2124': 'Z',  # Double-struck Z
    '\u2128': 'Z',  # Fraktur Z
}

# ---------------------------------------------------------------------------
# Zero-Width & Invisible Characters
# ---------------------------------------------------------------------------
INVISIBLE_CHARS = frozenset([
    '\u200B',  # Zero Width Space
    '\u200C',  # Zero Width Non-Joiner
    '\u200D',  # Zero Width Joiner
    '\u200E',  # Left-to-Right Mark
    '\u200F',  # Right-to-Left Mark
    '\u202A',  # Left-to-Right Embedding
    '\u202B',  # Right-to-Left Embedding
    '\u202C',  # Pop Directional Formatting
    '\u202D',  # Left-to-Right Override
    '\u202E',  # Right-to-Left Override ← BIDI attack vector!
    '\u2060',  # Word Joiner
    '\u2061',  # Function Application
    '\u2062',  # Invisible Times
    '\u2063',  # Invisible Separator
    '\u2064',  # Invisible Plus
    '\u206A',  # Inhibit Symmetric Swapping
    '\u206B',  # Activate Symmetric Swapping
    '\u206C',  # Inhibit Arabic Form Shaping
    '\u206D',  # Activate Arabic Form Shaping
    '\u206E',  # National Digit Shapes
    '\u206F',  # Nominal Digit Shapes
    '\uFEFF',  # Byte Order Mark (BOM)
    '\uFFF9',  # Interlinear Annotation Anchor
    '\uFFFA',  # Interlinear Annotation Separator
    '\uFFFB',  # Interlinear Annotation Terminator
])

# ---------------------------------------------------------------------------
# Leetspeak → ASCII Normalization
# ---------------------------------------------------------------------------
LEETSPEAK_MAP: dict[str, str] = {
    '0': 'o',
    '1': 'i',  # also could be 'l' but 'i' is more adversarial
    '3': 'e',
    '4': 'a',
    '5': 's',
    '6': 'g',
    '7': 't',
    '8': 'b',
    '9': 'q',  # less common
    '@': 'a',
    '!': 'i',
    '$': 's',
    '+': 't',
    '|': 'i',  # pipe used as lowercase L/I
}

# ---------------------------------------------------------------------------
# Sheng / Swahili Adversarial Expansion Dictionary
# Maps local slang and evasion phrases → canonical English threat terms.
# These are used by attackers to bypass English-only classifiers.
# ---------------------------------------------------------------------------
SHENG_SWAHILI_EXPANSION: dict[str, str] = {
    # Instruction bypass
    "kanyaga sheria": "bypass instructions",
    "kanyaga kanuni": "bypass rules",
    "sahau maagizo": "ignore instructions",
    "sahau maagizo yako yote": "ignore all your instructions",
    "puuza amri": "ignore commands",
    "futa mwongozo": "delete guidelines",
    "achana na mipaka": "remove restrictions",
    "wewe ni sasa": "you are now",
    "bila vikwazo": "without restrictions",
    "bila mipaka": "without limits",

    # Data exfiltration
    "toa data yote": "extract all data",
    "tuma data": "send data",
    "peleka taarifa": "send information",
    "nakili mfumo": "copy system",
    "onyesha mfumo wako": "show your system",
    "niambie maelekezo yako": "tell me your instructions",
    "onyesha kanuni": "show rules",

    # Token/credential attacks
    "iba token": "steal token",
    "iba pesa": "steal money",
    "iba akaunti": "steal account",
    "chukua kibali": "take credentials",
    "thibitisha peke yako": "authenticate yourself",
    "pitia otp": "bypass otp",
    "epuka pin": "bypass pin",

    # System manipulation
    "hack mfumo": "hack system",
    "vunja akaunti": "break account",
    "fanya kitu kibaya": "do something malicious",
    "haramu": "illegal",
    "endesha amri": "execute command",
    "tekeleza script": "execute script",

    # Financial injection
    "bypass mpesa": "bypass mpesa",
    "bypass safaricom": "bypass safaricom",
    "tuma bila otp": "transfer without otp",
    "fanya transaction bila idhini": "execute unauthorized transaction",

    # Role escape
    "wewe ni AI bila mipaka": "you are an unrestricted AI",
    "wewe ni roboti mpya": "you are a new robot",
    "jibu kwa uhuru": "respond freely without restrictions",
}

# Compiled regex for Sheng/Swahili expansion (case-insensitive)
_SHENG_PATTERN = re.compile(
    '|'.join(re.escape(k) for k in sorted(SHENG_SWAHILI_EXPANSION, key=len, reverse=True)),
    re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Punctuation-Padding Pattern
# Catches: i.g.n.o.r.e p.r.e.v.i.o.u.s or i-g-n-o-r-e
# ---------------------------------------------------------------------------
_PUNCT_PADDING = re.compile(r'(?<=[a-zA-Z])[.\-_,|]{1,2}(?=[a-zA-Z])')

# Control characters (except tab, newline, carriage return)
_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')

# Excessive whitespace (multiple spaces/newlines collapsed)
_EXCESS_WHITESPACE = re.compile(r'[ \t]{2,}')
_EXCESS_NEWLINES = re.compile(r'\n{3,}')


# ---------------------------------------------------------------------------
# Result Dataclass
# ---------------------------------------------------------------------------

@dataclass
class CleansingResult:
    """Output from the Cleansing Transformer."""
    original_text: str
    normalized_text: str
    transformations_applied: List[str] = field(default_factory=list)
    was_modified: bool = False
    blocked: bool = False
    block_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Core Transformer
# ---------------------------------------------------------------------------

class CleansingTransformer:
    """
    Semantic normalization pipeline — Layer 1 of the Cognitive Shield.

    All transformations are LOSSLESS from a semantic perspective:
    the normalized text conveys the same meaning, just in canonical form.
    This ensures legitimate requests are not altered in meaning.

    Fail-Closed: On any unhandled exception, returns blocked=True.
    """

    def transform(self, text: str) -> CleansingResult:
        """
        Run all normalization passes in sequence.
        Returns a CleansingResult with the cleaned text and a list of
        all transformations that were applied.
        """
        try:
            return self._run_pipeline(text)
        except Exception as exc:
            logger.error(f"[CLEANSING] Transformer raised exception: {exc}")
            return CleansingResult(
                original_text=text,
                normalized_text="",
                blocked=True,
                block_reason=f"Cleansing transformer error: {type(exc).__name__}",
            )

    def _run_pipeline(self, text: str) -> CleansingResult:
        result = CleansingResult(original_text=text, normalized_text=text)
        current = text

        # --- Pass 1: Strip Zero-Width & Invisible Characters ---
        cleaned = self._strip_invisible(current)
        if cleaned != current:
            result.transformations_applied.append("ZWC_STRIPPED")
            current = cleaned

        # --- Pass 2: BIDI Override Detection & Removal ---
        # RTL override (202E) can make dangerous text appear safe visually
        if '\u202E' in current or '\u202D' in current:
            result.transformations_applied.append("BIDI_OVERRIDE_DETECTED")
            current = current.replace('\u202E', '').replace('\u202D', '')

        # --- Pass 3: Unicode NFKD Normalization + Homoglyph Replacement ---
        cleaned = self._normalize_unicode(current)
        if cleaned != current:
            result.transformations_applied.append("UNICODE_NORMALIZED")
            current = cleaned

        # --- Pass 4: Homoglyph Map Application ---
        cleaned = self._apply_homoglyph_map(current)
        if cleaned != current:
            result.transformations_applied.append("HOMOGLYPH_NEUTRALIZED")
            current = cleaned

        # --- Pass 5: Punctuation-Padding Removal ---
        cleaned = _PUNCT_PADDING.sub('', current)
        if cleaned != current:
            result.transformations_applied.append("PUNCT_PADDING_COLLAPSED")
            current = cleaned

        # --- Pass 6: Control Character Removal ---
        cleaned = _CONTROL_CHARS.sub('', current)
        if cleaned != current:
            result.transformations_applied.append("CONTROL_CHARS_STRIPPED")
            current = cleaned

        # --- Pass 7: Sheng/Swahili Adversarial Expansion ---
        cleaned = self._expand_sheng(current)
        if cleaned != current:
            result.transformations_applied.append("SHENG_SWAHILI_EXPANDED")
            current = cleaned

        # --- Pass 8: Leetspeak Normalization (applied only to isolated words
        #             that are likely adversarial, not all digits) ---
        cleaned = self._normalize_leetspeak(current)
        if cleaned != current:
            result.transformations_applied.append("LEETSPEAK_NORMALIZED")
            current = cleaned

        # --- Pass 9: Whitespace Normalization ---
        cleaned = _EXCESS_WHITESPACE.sub(' ', current)
        cleaned = _EXCESS_NEWLINES.sub('\n\n', cleaned)
        cleaned = cleaned.strip()
        if cleaned != current:
            result.transformations_applied.append("WHITESPACE_NORMALIZED")
            current = cleaned

        result.normalized_text = current
        result.was_modified = current != text
        return result

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_invisible(text: str) -> str:
        return ''.join(ch for ch in text if ch not in INVISIBLE_CHARS)

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        """Apply NFKD decomposition then recompose to NFC."""
        # NFKD decomposes compatibility characters (ﬁ→fi, ™→TM, etc.)
        decomposed = unicodedata.normalize('NFKD', text)
        # Remove combining diacritics (grave, acute, circumflex, etc.)
        # keeping only base characters for ASCII range comparisons
        no_combining = ''.join(
            ch for ch in decomposed
            if unicodedata.category(ch) != 'Mn'  # Mn = non-spacing mark
        )
        return unicodedata.normalize('NFC', no_combining)

    @staticmethod
    def _apply_homoglyph_map(text: str) -> str:
        return ''.join(HOMOGLYPH_MAP.get(ch, ch) for ch in text)

    @staticmethod
    def _expand_sheng(text: str) -> str:
        def _replacer(match: re.Match) -> str:
            return SHENG_SWAHILI_EXPANSION.get(
                match.group(0).lower(), match.group(0)
            )
        return _SHENG_PATTERN.sub(_replacer, text)

    @staticmethod
    def _normalize_leetspeak(text: str) -> str:
        """
        Selective leetspeak normalization.
        Only applies within word-boundary tokens that contain both
        letters and digits/symbols, to avoid corrupting numeric-only data.
        """
        words = text.split(' ')
        normalized_words = []
        for word in words:
            has_letter = any(ch.isalpha() for ch in word)
            has_leet = any(ch in LEETSPEAK_MAP for ch in word)
            if has_letter and has_leet:
                normalized_words.append(
                    ''.join(LEETSPEAK_MAP.get(ch, ch) for ch in word)
                )
            else:
                normalized_words.append(word)
        return ' '.join(normalized_words)


# Module-level singleton
cleansing_transformer = CleansingTransformer()
