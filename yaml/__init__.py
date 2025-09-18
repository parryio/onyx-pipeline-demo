"""Minimal YAML loader used for deterministic offline pipeline tests.

This implementation intentionally supports only the YAML constructs that
appear in the repository configuration and lexicon files:

* Mappings with string keys.
* Nested mappings determined by indentation.
* Sequences introduced via ``-`` markers.
* Inline scalars (strings, numbers, booleans, ``null``) and flow
  collection literals (``[]``/``{}``).

The goal is not to be a full YAML parser but to provide a deterministic,
pure-Python ``safe_load`` replacement so that the test suite can execute in
environments without PyYAML installed or without network access to install
it.
"""

from __future__ import annotations

import ast
from typing import Any, List, Sequence, Tuple


def safe_load(text: str | bytes | None) -> Any:
    """Parse a YAML string into native Python objects.

    The supported feature subset is deliberately small but sufficient for
    the project fixtures. When parsing fails the function raises ``ValueError``.
    """

    if text is None:
        return None
    if hasattr(text, 'read'):
        text = text.read()
    if isinstance(text, bytes):
        text = text.decode('utf-8')

    lines = _preprocess(text)
    if not lines:
        return None

    node, index = _parse_node(lines, 0)
    if index != len(lines):
        # Guard against trailing content at a different indentation level.
        raise ValueError('YAML parse did not consume all input')
    return node


def _preprocess(text: str) -> List[Tuple[int, str]]:
    """Convert raw YAML text into ``(indent, content)`` tuples."""

    processed: List[Tuple[int, str]] = []
    for raw_line in text.splitlines():
        stripped = _strip_comment(raw_line.rstrip())
        if not stripped:
            continue
        indent = len(stripped) - len(stripped.lstrip(' '))
        content = stripped[indent:]
        if content in {'---', '...'}:
            continue
        processed.append((indent, content))
    return processed


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    out_chars: List[str] = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == '#' and not in_single and not in_double:
            break
        out_chars.append(ch)
    return ''.join(out_chars).rstrip()


def _parse_node(lines: Sequence[Tuple[int, str]], index: int) -> Tuple[Any, int]:
    indent, content = lines[index]
    if content.startswith('- '):
        return _parse_sequence(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines: Sequence[Tuple[int, str]], index: int, indent: int) -> Tuple[Any, int]:
    mapping: dict[str, Any] = {}
    i = index
    while i < len(lines):
        cur_indent, content = lines[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError('Invalid indentation for mapping entry')
        if content.startswith('- '):
            break
        key, sep, rest = content.partition(':')
        if not sep:
            raise ValueError(f'Invalid mapping entry: {content!r}')
        key = key.strip()
        rest = rest.strip()
        i += 1
        if rest:
            mapping[key] = _parse_scalar(rest)
            continue
        if i >= len(lines) or lines[i][0] <= indent:
            mapping[key] = None
            continue
        child_indent = lines[i][0]
        child, i = _parse_node(lines, i)
        mapping[key] = child
    return mapping, i


def _parse_sequence(lines: Sequence[Tuple[int, str]], index: int, indent: int) -> Tuple[Any, int]:
    seq: List[Any] = []
    i = index
    while i < len(lines):
        cur_indent, content = lines[i]
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError('Invalid indentation for sequence entry')
        if not content.startswith('- '):
            break
        item_content = content[2:].strip()
        i += 1

        inline_item: Any = None
        inline_is_mapping = False
        inline_key = None
        if item_content:
            if ':' in item_content:
                inline_is_mapping = True
                key, _, rest = item_content.partition(':')
                inline_key = key.strip()
                rest = rest.strip()
                inline_item = {inline_key: _parse_scalar(rest) if rest else None}
            else:
                inline_item = _parse_scalar(item_content)

        child = None
        if i < len(lines) and lines[i][0] > indent:
            child, i = _parse_node(lines, i)

        if inline_is_mapping:
            assert inline_key is not None
            assert isinstance(inline_item, dict)
            current_val = inline_item.get(inline_key)
            if isinstance(child, dict):
                if current_val is None:
                    inline_item[inline_key] = child
                else:
                    inline_item.update(child)
            elif child is not None:
                inline_item[inline_key] = child if current_val in (None, []) else current_val
            seq.append(inline_item)
        else:
            if child is None:
                seq.append(inline_item)
            else:
                if inline_item in (None, []):
                    seq.append(child)
                elif isinstance(child, dict):
                    merged = {'value': inline_item}
                    merged.update(child)
                    seq.append(merged)
                else:
                    seq.append(inline_item)
                    seq.append(child)
    return seq, i


def _parse_scalar(token: str) -> Any:
    token = token.strip()
    if not token:
        return ''
    lowered = token.lower()
    if lowered in {'null', 'none', '~'}:
        return None
    if lowered == 'true':
        return True
    if lowered == 'false':
        return False
    try:
        if token[0] in {'"', "'"}:
            return ast.literal_eval(token)
        if token[0] in {'[', '{'}:
            return ast.literal_eval(token)
        if token.isdigit() or (token.startswith('-') and token[1:].isdigit()):
            return int(token)
        if _looks_like_float(token):
            return float(token)
    except Exception:
        pass
    return token


def _looks_like_float(token: str) -> bool:
    if token.count('.') != 1:
        return False
    left, right = token.split('.', 1)
    if left.startswith('-'):
        left = left[1:]
    return left.isdigit() and right.isdigit()


__all__ = ['safe_load']
