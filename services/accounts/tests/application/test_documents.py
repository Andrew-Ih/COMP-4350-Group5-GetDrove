"""Uploading and opening driver documents (#9), with in-memory fakes."""

from uuid import uuid4

import pytest

from accounts.application.documents import OpenDriverDocument, UploadDriverDocuments
from accounts.domain.documents import DocumentKind
from accounts.domain.driver import DriverProfile, DriverStatus, Vehicle
from accounts.domain.errors import (
    DocumentNotFoundError,
    DriverAlreadyApprovedError,
    UnsupportedFileTypeError,
)
from accounts.testing import FIXED_NOW, FakeClock, FakeDocumentStorage, FakeUnitOfWork

PDF = b"%PDF-1.7 licence"
PNG = b"\x89PNG\r\n\x1a\n insurance"


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def storage() -> FakeDocumentStorage:
    return FakeDocumentStorage()


@pytest.fixture
def upload(uow: FakeUnitOfWork, storage: FakeDocumentStorage) -> UploadDriverDocuments:
    return UploadDriverDocuments(uow, storage, FakeClock())


async def test_uploading_saves_both_files_and_makes_the_application_pending(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage, upload: UploadDriverDocuments
) -> None:
    user_id = uuid4()

    profile = await upload(user_id, PDF, PNG)

    saved = uow.drivers.rows[user_id]
    assert saved.status is DriverStatus.PENDING
    assert saved.submitted_at == FIXED_NOW
    assert saved.licence_key is not None and saved.insurance_key is not None
    assert saved.licence_key.startswith(f"{user_id}/licence-")
    assert saved.licence_key.endswith(".pdf")
    assert saved.insurance_key.endswith(".png")
    assert storage.files == {saved.licence_key: PDF, saved.insurance_key: PNG}
    assert profile == saved
    assert uow.committed


async def test_uploading_again_replaces_the_files_and_deletes_the_old_ones(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage, upload: UploadDriverDocuments
) -> None:
    user_id = uuid4()
    first = await upload(user_id, PDF, PNG)

    second = await upload(user_id, b"%PDF-new licence", b"%PDF-new insurance")

    assert second.licence_key != first.licence_key
    assert set(storage.files) == {second.licence_key, second.insurance_key}


async def test_a_rejected_driver_can_upload_again(
    uow: FakeUnitOfWork, upload: UploadDriverDocuments
) -> None:
    user_id = uuid4()
    await upload(user_id, PDF, PNG)
    profile = uow.drivers.rows[user_id]
    profile.reject(uuid4(), "Blurry licence.", FIXED_NOW)

    again = await upload(user_id, PDF, PNG)

    assert again.status is DriverStatus.PENDING
    assert again.rejection_reason is None


async def test_the_vehicle_is_kept_when_documents_are_uploaded(
    uow: FakeUnitOfWork, upload: UploadDriverDocuments
) -> None:
    user_id = uuid4()
    civic = Vehicle.create("Honda", "Civic", "Blue", "ABC123")
    await uow.drivers.save(DriverProfile(user_id, vehicle=civic))

    profile = await upload(user_id, PDF, PNG)

    assert profile.vehicle == civic


async def test_an_approved_driver_cant_upload_and_nothing_is_saved(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage, upload: UploadDriverDocuments
) -> None:
    user_id = uuid4()
    approved = DriverProfile(user_id, vehicle=Vehicle.create("Honda", "Civic", "Blue", "AB1"))
    approved.submit_documents(
        f"{user_id}/licence-old.pdf", f"{user_id}/insurance-old.pdf", FIXED_NOW
    )
    approved.approve(uuid4(), FIXED_NOW)
    await uow.drivers.save(approved)
    uow.committed = False

    with pytest.raises(DriverAlreadyApprovedError):
        await upload(user_id, PDF, PNG)

    assert storage.files == {}
    assert uow.drivers.rows[user_id].licence_key == f"{user_id}/licence-old.pdf"
    assert not uow.committed


async def test_a_bad_second_file_saves_nothing(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage, upload: UploadDriverDocuments
) -> None:
    with pytest.raises(UnsupportedFileTypeError):
        await upload(uuid4(), PDF, b"not an image")

    assert storage.files == {}
    assert uow.drivers.rows == {}
    assert not uow.committed


async def test_if_saving_fails_no_new_file_is_left_behind(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage, upload: UploadDriverDocuments
) -> None:
    user_id = uuid4()
    first = await upload(user_id, PDF, PNG)
    uow.committed = False
    storage.fail_on_save = True

    with pytest.raises(OSError, match="disk full"):
        await upload(user_id, PDF, PNG)

    # The first upload's files are untouched; nothing from the failed one remains.
    assert set(storage.files) == {first.licence_key, first.insurance_key}
    assert not uow.committed


# ---------------------------------------------------------------- opening a document


async def test_opening_a_document_returns_it_with_its_type(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage, upload: UploadDriverDocuments
) -> None:
    user_id = uuid4()
    await upload(user_id, PDF, PNG)
    open_document = OpenDriverDocument(uow, storage)

    licence = await open_document(user_id, DocumentKind.LICENCE)
    insurance = await open_document(user_id, DocumentKind.INSURANCE)

    assert (licence.content, licence.content_type) == (PDF, "application/pdf")
    assert (insurance.content, insurance.content_type) == (PNG, "image/png")


async def test_no_application_is_document_not_found(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage
) -> None:
    with pytest.raises(DocumentNotFoundError):
        await OpenDriverDocument(uow, storage)(uuid4(), DocumentKind.LICENCE)


async def test_a_vehicle_but_no_documents_is_document_not_found(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage
) -> None:
    user_id = uuid4()
    await uow.drivers.save(
        DriverProfile(user_id, vehicle=Vehicle.create("Honda", "Civic", "Blue", "AB1"))
    )

    with pytest.raises(DocumentNotFoundError):
        await OpenDriverDocument(uow, storage)(user_id, DocumentKind.INSURANCE)


async def test_a_file_missing_from_storage_is_document_not_found(
    uow: FakeUnitOfWork, storage: FakeDocumentStorage, upload: UploadDriverDocuments
) -> None:
    user_id = uuid4()
    profile = await upload(user_id, PDF, PNG)
    assert profile.licence_key is not None
    storage.files.pop(profile.licence_key)

    with pytest.raises(DocumentNotFoundError):
        await OpenDriverDocument(uow, storage)(user_id, DocumentKind.LICENCE)
