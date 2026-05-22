from typing import Iterable

import fitz


def _page_text(page: fitz.Page) -> str:
    text = page.get_text("text", sort=True).strip()
    if text:
        return text
    blocks = page.get_text("blocks")
    parts: list[str] = []
    for block in blocks:
        if len(block) >= 5 and isinstance(block[4], str):
            snippet = block[4].strip()
            if snippet:
                parts.append(snippet)
    return "\n".join(parts).strip()


def extract_text_by_page(pdf_path: str) -> list[str]:
    doc = fitz.open(pdf_path)
    try:
        return [_page_text(page) for page in doc]
    finally:
        doc.close()


def pdf_text_stats(pages: list[str]) -> dict[str, int]:
    non_empty_pages = sum(1 for page in pages if page.strip())
    total_chars = sum(len(page) for page in pages)
    return {
        "pages": len(pages),
        "non_empty_pages": non_empty_pages,
        "total_chars": total_chars,
    }


def chunk_text(
    pages: list[str],
    max_chars: int = 4500,
    overlap: int = 300,
) -> Iterable[tuple[str, int, int]]:
    buffer = ""
    page_start = 1
    page_end = 1

    for index, page_text in enumerate(pages, start=1):
        if not buffer:
            page_start = index
        page_end = index

        if len(buffer) + len(page_text) <= max_chars:
            buffer += page_text + "\n"
            continue

        yield buffer.strip(), page_start, page_end
        buffer = buffer[-overlap:] + page_text + "\n"
        page_start = index

    if buffer.strip():
        yield buffer.strip(), page_start, page_end
