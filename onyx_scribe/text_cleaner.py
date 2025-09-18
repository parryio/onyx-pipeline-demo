import re
import unicodedata
from typing import List

CONTROL_RE = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
WHITESPACE_RE = re.compile(r'\s+')
TOKEN_RE = re.compile(r'\w+|[^\w\s]', re.UNICODE)

def clean_text(text: str, max_token_length: int = 120) -> str:
    """Deterministic, PDR-compliant text normalization.

    Steps:
      1. Unicode NFKC normalization.
      2. Strip control characters (except TAB, LF which chunk boundaries rely on earlier pipeline logic for splitting).
      3. Collapse all whitespace runs to a single space.
      4. Token filter: remove tokens that are purely punctuation repeated (>8) or exceed max_token_length.
      5. Return a single trailing-space-trimmed string.
    The transformation is pure and idempotent.
    """
    if not text:
        return ''
    # 1. NFKC
    norm = unicodedata.normalize('NFKC', text)
    # 2. Remove control chars (keep \n and \t so higher-level logic can still treat them deterministically if needed)
    norm = CONTROL_RE.sub('', norm)
    # 3. Collapse whitespace
    norm = WHITESPACE_RE.sub(' ', norm).strip()
    if not norm:
        return ''
    # 4. Token pass
    out_tokens: List[str] = []
    for tok in TOKEN_RE.findall(norm):
        if len(tok) > max_token_length:
            continue
        if len(tok) > 8 and all(ch == tok[0] for ch in tok) and not tok[0].isalnum():
            # skip pathological punctuation runs (e.g. "!!!!!!!!!!!!")
            continue
        out_tokens.append(tok)
    cleaned = ' '.join(out_tokens)
    # 5. Final collapse in case token join introduced double spaces
    cleaned = WHITESPACE_RE.sub(' ', cleaned).strip()
    return cleaned

__all__ = ["clean_text"]