from typing import Iterable

import fitz


def extract_text_by_page(pdf_path: str) -> list[str]:
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    return pages


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
