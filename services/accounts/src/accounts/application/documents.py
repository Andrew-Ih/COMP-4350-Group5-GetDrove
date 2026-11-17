"""Use cases for driver documents (#9): uploading them, and opening one."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from accounts.application.ports import Clock, DocumentStorage, UnitOfWork
from accounts.domain.documents import EXTENSIONS, Document, DocumentKind
from accounts.domain.driver import DriverProfile
from accounts.domain.errors import DocumentNotFoundError


@dataclass(frozen=True)
class StoredDocument:
    content: bytes
    content_type: str


def _content_type(key: str) -> str:
    return next(type_ for type_, extension in EXTENSIONS.items() if key.endswith(extension))


class UploadDriverDocuments:
    """PUT /me/driver/documents: saves both files and sets the application to pending, so an
    admin reviews it. Replaces earlier files, e.g. after a rejection. 409
    driver_already_approved once approved."""

    def __init__(self, uow: UnitOfWork, storage: DocumentStorage, clock: Clock) -> None:
        self._uow = uow
        self._storage = storage
        self._clock = clock

    async def __call__(self, user_id: UUID, licence: bytes, insurance: bytes) -> DriverProfile:
        # Checked before anything is saved, so a bad second file leaves no first file behind.
        documents = [
            Document.check(DocumentKind.LICENCE, licence),
            Document.check(DocumentKind.INSURANCE, insurance),
        ]
        async with self._uow as uow:
            profile = await uow.drivers.get(user_id, for_update=True) or DriverProfile(user_id)
            old_keys = [key for key in (profile.licence_key, profile.insurance_key) if key]
            # New names each time: the old files stay valid until the change is committed.
            keys = [
                f"{user_id}/{document.kind.value}-{uuid4().hex}{EXTENSIONS[document.content_type]}"
                for document in documents
            ]
            profile.submit_documents(keys[0], keys[1], self._clock.now())  # 409 if approved
            try:
                for key, document in zip(keys, documents, strict=True):
                    await self._storage.save(key, document.content)
                await uow.drivers.save(profile)
                await uow.commit()
            except BaseException:
                for key in keys:
                    await self._storage.delete(key)
                raise
        for key in old_keys:
            await self._storage.delete(key)
        return profile


class OpenDriverDocument:
    """GET /me/driver/documents/{kind} (the driver's own) and
    GET /admin/drivers/{userId}/documents/{kind} (admins): 404 document_not_found if it
    hasn't been uploaded. Who may call it is checked by the endpoint."""

    def __init__(self, uow: UnitOfWork, storage: DocumentStorage) -> None:
        self._uow = uow
        self._storage = storage

    async def __call__(self, user_id: UUID, kind: DocumentKind) -> StoredDocument:
        async with self._uow as uow:
            profile = await uow.drivers.get(user_id)
        key = None
        if profile is not None:
            key = profile.licence_key if kind is DocumentKind.LICENCE else profile.insurance_key
        content = await self._storage.read(key) if key else None
        if key is None or content is None:
            raise DocumentNotFoundError(f"No {kind.value} has been uploaded.")
        return StoredDocument(content, _content_type(key))
