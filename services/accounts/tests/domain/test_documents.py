"""Driver documents (#9): only real PDF, JPEG and PNG files up to 5 MB."""

import pytest

from accounts.domain.documents import MAX_DOCUMENT_BYTES, Document, DocumentKind
from accounts.domain.errors import FileTooLargeError, UnsupportedFileTypeError

PDF = b"%PDF-1.7\n..."
JPEG = b"\xff\xd8\xff\xe0..."
PNG = b"\x89PNG\r\n\x1a\n..."


@pytest.mark.parametrize(
    ("content", "content_type"),
    [(PDF, "application/pdf"), (JPEG, "image/jpeg"), (PNG, "image/png")],
)
def test_pdf_jpeg_and_png_are_accepted(content: bytes, content_type: str) -> None:
    document = Document.check(DocumentKind.LICENCE, content)

    assert document.content_type == content_type
    assert document.content == content


def test_the_type_comes_from_the_content_not_the_name() -> None:
    # A text file renamed to licence.pdf still starts with text.
    with pytest.raises(UnsupportedFileTypeError) as raised:
        Document.check(DocumentKind.INSURANCE, b"just some text, renamed to .pdf")

    assert [error.field for error in raised.value.errors] == ["insurance"]


def test_exactly_5_mb_is_accepted() -> None:
    content = PDF + b"0" * (MAX_DOCUMENT_BYTES - len(PDF))

    assert Document.check(DocumentKind.LICENCE, content).content_type == "application/pdf"


@pytest.mark.parametrize("content", [b"", PDF + b"0" * MAX_DOCUMENT_BYTES])
def test_empty_or_over_5_mb_is_refused(content: bytes) -> None:
    with pytest.raises(FileTooLargeError) as raised:
        Document.check(DocumentKind.LICENCE, content)

    assert [error.field for error in raised.value.errors] == ["licence"]
