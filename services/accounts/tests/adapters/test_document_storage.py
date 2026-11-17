"""FileDocumentStorage (#9): files in a folder, which is a Docker volume when deployed."""

from pathlib import Path
from uuid import uuid4

import pytest

from accounts.adapters.document_storage import FileDocumentStorage

KEY = f"{uuid4()}/licence-{uuid4().hex}.pdf"


def files_on_disk(root: Path) -> dict[str, bytes]:
    """Every file under ``root``, by its path relative to it, with ``/`` like the storage keys
    (on Windows, ``str()`` of a path would use backslashes)."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


async def test_saving_reading_and_deleting(tmp_path: Path) -> None:
    storage = FileDocumentStorage(tmp_path)

    await storage.save(KEY, b"%PDF-1")

    assert await storage.read(KEY) == b"%PDF-1"
    # Only the file itself: no half-written ".part" file left behind.
    assert files_on_disk(tmp_path) == {KEY: b"%PDF-1"}

    await storage.delete(KEY)

    assert await storage.read(KEY) is None
    await storage.delete(KEY)  # deleting again is fine


async def test_saving_again_replaces_the_file(tmp_path: Path) -> None:
    storage = FileDocumentStorage(tmp_path)
    await storage.save(KEY, b"old")

    await storage.save(KEY, b"new")

    assert await storage.read(KEY) == b"new"


async def test_a_missing_file_is_none(tmp_path: Path) -> None:
    assert await FileDocumentStorage(tmp_path).read(KEY) is None


@pytest.mark.parametrize(
    "key",
    ["../../etc/passwd", f"{uuid4()}/../../secret.pdf", "/etc/passwd", "licence.pdf", ""],
)
async def test_keys_that_could_point_outside_the_folder_are_refused(
    tmp_path: Path, key: str
) -> None:
    storage = FileDocumentStorage(tmp_path / "documents")

    with pytest.raises(ValueError, match="Not a document key"):
        await storage.read(key)
    with pytest.raises(ValueError, match="Not a document key"):
        await storage.save(key, b"x")
