"""Driver documents (#9): the licence and insurance an admin checks before approving.

Only PDF, JPEG and PNG files up to 5 MB are accepted. The type is read from the file's
first bytes, not from its name or the browser's claim, so a renamed file can't get through.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from accounts.domain.errors import FileTooLargeError, UnsupportedFileTypeError
from common_web import InvalidField

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024

# The first bytes of each accepted file type, and the type it's served back as.
_SIGNATURES = {
    b"%PDF-": "application/pdf",
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
}
EXTENSIONS = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}


class DocumentKind(StrEnum):
    LICENCE = "licence"
    INSURANCE = "insurance"


@dataclass(frozen=True)
class Document:
    kind: DocumentKind
    content: bytes
    content_type: str

    @classmethod
    def check(cls, kind: DocumentKind, content: bytes) -> Self:
        """422 file_too_large over 5 MB (or empty), 422 unsupported_file_type unless it's a
        PDF, JPEG or PNG."""
        if not content or len(content) > MAX_DOCUMENT_BYTES:
            raise FileTooLargeError(
                "Files must be 5 MB or smaller.",
                [InvalidField(kind.value, "Choose a file up to 5 MB")],
            )
        content_type = next(
            (type_ for magic, type_ in _SIGNATURES.items() if content.startswith(magic)), None
        )
        if content_type is None:
            raise UnsupportedFileTypeError(
                "Use a PDF, JPEG or PNG file.",
                [InvalidField(kind.value, "Must be a PDF, JPEG or PNG")],
            )
        return cls(kind, content, content_type)
