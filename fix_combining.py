"""
Fix combining-mark span boundaries in the pre-built surah HTML files.

Two patterns break Arabic text shaping:

  Pattern A  TEXT_NODE <span class="r-X">COMBINING_MARK
             → move the preceding base+marks cluster INTO the span
             → TEXT_NODE_MINUS_CLUSTER <span class="r-X">CLUSTER+COMBINING_MARK

  Pattern B  </span> <span class="r-X">COMBINING_MARK
             → move the combining mark BACK into the preceding span
             → COMBINING_MARK</span> <span class="r-X">

Both ensure a <span> boundary never separates a base letter from its
diacritics, which is required for the browser's Arabic shaping engine.

Run from the project root:  python fix_combining.py
"""

import glob
import os
import re
import unicodedata

SURAHS_DIR = os.path.join(os.path.dirname(__file__), 'surahs')

# Arabic combining-mark characters (same ranges used in the JS runtime fix)
_CM = (
    'ً-ٟ'   # harakat, shadda, sukun, tanwin
    'ٰ'           # superscript alef  ← the main visible culprit
    'ۖ-ۜ'   # Quranic annotation signs
    '۟-ۤ'
    'ۧ-ۨ'
)
_CM_CLASS = f'[{_CM}]'


def is_combining(ch: str) -> bool:
    return unicodedata.category(ch) in ('Mn', 'Mc', 'Me')


def last_cluster_split(s: str) -> tuple[str, str]:
    """(before, last_grapheme_cluster) — cluster is base char + trailing combining marks."""
    if not s:
        return '', ''
    pos = len(s) - 1
    while pos > 0 and is_combining(s[pos]):
        pos -= 1
    return s[:pos], s[pos:]


# ── Pattern A ──────────────────────────────────────────────────────────────
# Arabic text run immediately before a span whose first char is a combining mark.
# Lookahead keeps the combining mark unconsumed so it stays inside the span.
PATTERN_A = re.compile(
    r'([؀-ۿ]+)'          # group 1: Arabic text (base chars + their diacritics)
    r'(<span\b[^>]*>)'    # group 2: span opening tag
    r'(?=' + _CM_CLASS + ')',
    re.UNICODE,
)


def fix_a(m: re.Match) -> str:
    before, cluster = last_cluster_split(m.group(1))
    return before + m.group(2) + cluster


# ── Pattern B ──────────────────────────────────────────────────────────────
# A span closing tag immediately before another span that starts with a
# combining mark.  Move the mark before the closing tag so it sits inside
# the preceding span alongside its base letter.
PATTERN_B = re.compile(
    r'(</span>)'           # group 1: closing tag of the base-letter span
    r'(<span\b[^>]*>)'    # group 2: opening tag of the combining-mark span
    r'(' + _CM_CLASS + ')',  # group 3: the combining mark (consumed here)
    re.UNICODE,
)


def fix_b(m: re.Match) -> str:
    # Result: COMBINING_MARK + </span> + <span...>
    # The mark moves into the preceding span; the new span starts after.
    return m.group(3) + m.group(1) + m.group(2)


def fix_file(path: str) -> int:
    with open(path, encoding='utf-8') as f:
        content = f.read()

    # Apply both patterns; loop until stable (each pass can expose new instances).
    for _ in range(10):
        updated = PATTERN_B.sub(fix_b, PATTERN_A.sub(fix_a, content))
        if updated == content:
            break
        content = updated

    if updated == open(path, encoding='utf-8').read():
        return 0

    with open(path, 'w', encoding='utf-8') as f:
        f.write(updated)
    return 1


def main() -> None:
    files = sorted(glob.glob(os.path.join(SURAHS_DIR, '*.html')))
    if not files:
        print(f'No HTML files found in {SURAHS_DIR}')
        return

    changed = 0
    for path in files:
        changed += fix_file(path)

    print(f'{changed} / {len(files)} files updated.')


if __name__ == '__main__':
    main()
