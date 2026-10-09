"""Resolve MCQ answers against the frozen option list, never the live bank."""
import string


def option_index(answer: object, options: object) -> int | None:
    if not isinstance(answer, str) or not isinstance(options, list):
        return None
    value = answer.strip().casefold()
    if not value:
        return None
    # Preserve literal text, including a choice whose text is itself a letter.
    texts = [(option.get('text') if isinstance(option, dict) else option) for option in options]
    matches = [i for i, text in enumerate(texts)
               if isinstance(text, str) and text.strip().casefold() == value]
    if matches:
        return matches[0] if len(matches) == 1 else None
    keys = [(option.get('key') if isinstance(option, dict) else string.ascii_uppercase[i])
            for i, option in enumerate(options[:26])]
    matches = [i for i, key in enumerate(keys)
               if isinstance(key, str) and key.strip().casefold() == value]
    if matches:
        return matches[0] if len(matches) == 1 else None
    # Common Arabic positional labels; do not normalize the option text itself
    # (أ/إ/ا can change the meaning of a scientific term).
    arabic = {'أ': 0, 'ا': 0, 'إ': 0, 'آ': 0, 'ب': 1, 'ج': 2, 'د': 3}
    index = arabic.get(value)
    return index if index is not None and index < len(options) else None
