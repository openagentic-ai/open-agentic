"""Text chunking with recursive character splitting."""


def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks using recursive character splitting.

    Tries each separator in order of preference. If a resulting piece is still
    larger than chunk_size, it recurses with the next separator.
    """
    if not text or not text.strip():
        return []

    if len(text) <= chunk_size:
        return [text]

    separators = ["\n\n", "\n", ". ", " ", ""]
    return _split_recursive(text, chunk_size, chunk_overlap, separators, 0)


def _split_recursive(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: list[str],
    sep_index: int,
) -> list[str]:
    """Recursively split text trying separators in order."""
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    if sep_index >= len(separators):
        return _merge_splits(
            [text[i : i + chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)],
            chunk_size,
            chunk_overlap,
            "",
        )

    separator = separators[sep_index]

    if separator == "":
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start += chunk_size - chunk_overlap
        return chunks

    parts = text.split(separator)

    if len(parts) == 1:
        return _split_recursive(text, chunk_size, chunk_overlap, separators, sep_index + 1)

    merged = _merge_splits(parts, chunk_size, chunk_overlap, separator)

    final: list[str] = []
    for chunk in merged:
        if len(chunk) <= chunk_size:
            final.append(chunk)
        else:
            final.extend(
                _split_recursive(chunk, chunk_size, chunk_overlap, separators, sep_index + 1)
            )

    return final


def _merge_splits(
    splits: list[str],
    chunk_size: int,
    chunk_overlap: int,
    separator: str,
) -> list[str]:
    """Merge small splits into chunks that respect chunk_size, with overlap."""
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for part in splits:
        part_len = len(part)
        sep_len = len(separator) if current_parts else 0

        if current_len + sep_len + part_len > chunk_size and current_parts:
            chunks.append(separator.join(current_parts))

            while current_len > chunk_overlap and len(current_parts) > 1:
                dropped = current_parts.pop(0)
                current_len -= len(dropped) + len(separator)

        current_parts.append(part)
        current_len = sum(len(p) for p in current_parts) + len(separator) * (len(current_parts) - 1)

    if current_parts:
        chunks.append(separator.join(current_parts))

    return chunks
