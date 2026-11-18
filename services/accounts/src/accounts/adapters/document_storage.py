"""The real ``DocumentStorage``: files in a directory, which is a Docker volume when the
service runs in Docker (ADR 0011). The volume needs backing up (#194)."""

import asyncio
import re
from pathlib import Path

# Keys are made by Accounts ("<user id>/<kind>-<hex>.<ext>"), never by a user, but they're
# checked anyway so a bad key can never point outside the directory.
_KEY = re.compile(r"[0-9a-f-]{36}/[a-z]+-[0-9a-f]{32}\.(pdf|jpg|png)")


class FileDocumentStorage:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise ValueError(f"Not a document key: {key!r}")
        return self._root / key

    async def save(self, key: str, content: bytes) -> None:
        await asyncio.to_thread(self._write, self._path(key), content)

    async def read(self, key: str) -> bytes | None:
        path = self._path(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            return None

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._path(key).unlink, missing_ok=True)

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written to a temporary name first, so a half-written file is never served.
        temporary = path.with_suffix(path.suffix + ".part")
        temporary.write_bytes(content)
        temporary.replace(path)
