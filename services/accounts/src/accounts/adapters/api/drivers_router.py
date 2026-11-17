"""Accounts API, Sprint 2 contract (#262): driver applications and approval, public
profiles, and the internal user lookups other services use.

Implemented: status (#10), documents (#9), vehicle (#125), admin approval (#127), and
the contacts lookup Notifications needs for emails (#146). Profiles and /internal/users
(#143) return 501 until their task implements them.
Paths are relative to the gateway prefix /api/accounts; /internal/... is only reachable
inside Docker (http://accounts:8000/internal/...).
"""

from typing import Annotated, Any, Literal, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from accounts.adapters.api.dependencies import AppClock, Documents, Uow
from accounts.adapters.api.schemas import (
    AdminDriver,
    DocumentKind,
    DocumentsUploaded,
    DriverProfile,
    DriverStatus,
    InternalContact,
    InternalContacts,
    InternalUsers,
    Problem,
    PublicProfile,
    RejectDriverRequest,
    Vehicle,
)
from accounts.application.admin import (
    Application,
    ApproveDriver,
    ListDriverApplications,
    RejectDriver,
)
from accounts.application.contacts import ListContacts
from accounts.application.documents import (
    OpenDriverDocument,
    StoredDocument,
    UploadDriverDocuments,
)
from accounts.application.drivers import GetMyDriverProfile, SaveVehicle
from accounts.domain import driver as domain
from accounts.domain.documents import MAX_DOCUMENT_BYTES
from accounts.domain.documents import DocumentKind as DomainDocumentKind
from common_security.dependencies import AuthenticatedUser, require_role
from common_security.user import CurrentUser

driver_router = APIRouter(prefix="/me/driver", tags=["drivers"])
admin_router = APIRouter(prefix="/admin/drivers", tags=["admin"])
profiles_router = APIRouter(tags=["users"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])

Responses = dict[int | str, dict[str, Any]]

Admin = Annotated[CurrentUser, Depends(require_role("admin"))]
"""A logged-in user with the admin role; anyone else gets 403 `forbidden`."""

UserIds = Annotated[
    list[UUID],
    Query(min_length=1, max_length=50, description="Repeat for each user: `?ids=...&ids=...`."),
]


def _problem(description: str, code: str) -> dict[str, Any]:
    return {"model": Problem, "description": f"{description} (code `{code}`)"}


def driver_profile_out(profile: domain.DriverProfile) -> DriverProfile:
    vehicle = profile.vehicle
    return DriverProfile(
        status=DriverStatus(profile.status.value),
        rejection_reason=profile.rejection_reason,
        documents=DocumentsUploaded(
            licence=profile.licence_key is not None, insurance=profile.insurance_key is not None
        ),
        vehicle=Vehicle(
            make=vehicle.make, model=vehicle.model, colour=vehicle.colour, plate=vehicle.plate
        )
        if vehicle
        else None,
        submitted_at=profile.submitted_at,
        reviewed_at=profile.reviewed_at,
    )


async def _read(upload: UploadFile) -> bytes:
    # One byte over the limit is enough to know it's too big, without reading the rest.
    return await upload.read(MAX_DOCUMENT_BYTES + 1)


def _file_response(document: StoredDocument) -> Response:
    return Response(
        content=document.content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": "inline",
            # Private documents: never kept by the browser or anything in between.
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def admin_driver_out(application: Application) -> AdminDriver:
    profile = driver_profile_out(application.profile)
    user = application.user
    return AdminDriver(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email.value,
        status=profile.status,
        vehicle=profile.vehicle,
        documents=profile.documents,
        submitted_at=profile.submitted_at,
        reviewed_at=profile.reviewed_at,
        rejection_reason=profile.rejection_reason,
    )


def _not_implemented() -> NoReturn:
    raise HTTPException(status_code=501, detail="Not implemented yet: this is a contract (#262).")


UNAUTHORIZED: Responses = {401: _problem("Missing or invalid access token", "unauthorized")}
INVALID: Responses = {422: _problem("Invalid input; `errors` lists the fields", "invalid_input")}
NOT_ADMIN: Responses = {
    **UNAUTHORIZED,
    403: _problem("Only admins can do this", "forbidden"),
}
DOCUMENT_FILE: Responses = {
    200: {
        "description": "The file as uploaded.",
        "content": {"application/pdf": {}, "image/jpeg": {}, "image/png": {}},
    },
    404: _problem("No document of this kind uploaded", "document_not_found"),
}


# ---------------------------------------------------------------- the driver's own application


@driver_router.get(
    "",
    summary="My driver status",
    description="Whether the logged-in user has applied to drive, and where it stands: "
    "`none`, `pending`, `approved` or `rejected` (with the reason).",
    responses=UNAUTHORIZED,
)
async def my_driver_profile(user: AuthenticatedUser, uow: Uow) -> DriverProfile:
    return driver_profile_out(await GetMyDriverProfile(uow)(user.id))


@driver_router.put(
    "/documents",
    summary="Upload my licence and insurance",
    description="Both files, PDF, JPEG or PNG, up to 5 MB each. Uploading (again, after a "
    "rejection) sets the status to `pending`. Only the driver and admins can open them.",
    responses={
        **UNAUTHORIZED,
        409: _problem("Already approved", "driver_already_approved"),
        422: _problem(
            "Invalid input, a file that isn't PDF, JPEG or PNG, or one over 5 MB",
            "invalid_input / unsupported_file_type / file_too_large",
        ),
    },
)
async def upload_documents(
    user: AuthenticatedUser,
    licence: Annotated[UploadFile, File(description="Driver's licence.")],
    insurance: Annotated[UploadFile, File(description="Proof of insurance.")],
    uow: Uow,
    storage: Documents,
    clock: AppClock,
) -> DriverProfile:
    profile = await UploadDriverDocuments(uow, storage, clock)(
        user.id, await _read(licence), await _read(insurance)
    )
    return driver_profile_out(profile)


@driver_router.get(
    "/documents/{kind}",
    summary="Open one of my documents",
    response_class=Response,
    responses={**UNAUTHORIZED, **INVALID, **DOCUMENT_FILE},
)
async def my_document(
    kind: DocumentKind, user: AuthenticatedUser, uow: Uow, storage: Documents
) -> Response:
    document = await OpenDriverDocument(uow, storage)(user.id, DomainDocumentKind(kind.value))
    return _file_response(document)


@driver_router.put(
    "/vehicle",
    summary="Save my vehicle",
    description="Make, model, colour and plate. The plate is stored in uppercase.",
    responses={**UNAUTHORIZED, **INVALID},
)
async def save_vehicle(body: Vehicle, user: AuthenticatedUser, uow: Uow) -> DriverProfile:
    profile = await SaveVehicle(uow)(user.id, body.make, body.model, body.colour, body.plate)
    return driver_profile_out(profile)


# ---------------------------------------------------------------- admin approval


@admin_router.get(
    "",
    summary="Driver applications",
    description="Applications with the given status, oldest first (default: pending). "
    "Students who never applied aren't applications, so `none` isn't accepted.",
    responses={**NOT_ADMIN, **INVALID},
)
async def list_drivers(
    admin: Admin,
    uow: Uow,
    status: Annotated[Literal["pending", "approved", "rejected"], Query()] = "pending",
) -> list[AdminDriver]:
    applications = await ListDriverApplications(uow)(domain.DriverStatus(status))
    return [admin_driver_out(application) for application in applications]


@admin_router.get(
    "/{user_id}/documents/{kind}",
    summary="Open a driver's document",
    response_class=Response,
    responses={**NOT_ADMIN, **INVALID, **DOCUMENT_FILE},
)
async def driver_document(
    user_id: UUID, kind: DocumentKind, admin: Admin, uow: Uow, storage: Documents
) -> Response:
    document = await OpenDriverDocument(uow, storage)(user_id, DomainDocumentKind(kind.value))
    return _file_response(document)


DECISION_ERRORS: Responses = {
    **NOT_ADMIN,
    **INVALID,
    404: _problem("No driver application for this user", "driver_not_found"),
    409: _problem("The application isn't pending", "driver_not_pending"),
}


@admin_router.post(
    "/{user_id}/approve",
    summary="Approve a driver",
    description="They can post trips straight away, without logging in again. Only an "
    "application with both documents and a saved vehicle can be approved, since riders need "
    "the vehicle to find their driver. Publishes `DriverApproved`.",
    responses={
        **DECISION_ERRORS,
        409: _problem(
            "The application isn't pending, or the driver hasn't saved a vehicle yet",
            "driver_not_pending / vehicle_missing",
        ),
    },
)
async def approve_driver(user_id: UUID, admin: Admin, uow: Uow, clock: AppClock) -> AdminDriver:
    return admin_driver_out(await ApproveDriver(uow, clock)(admin.id, user_id))


@admin_router.post(
    "/{user_id}/reject",
    summary="Reject a driver",
    description="The reason is shown to the driver, who can upload new documents. Publishes "
    "`DriverRejected`.",
    responses=DECISION_ERRORS,
)
async def reject_driver(
    user_id: UUID, body: RejectDriverRequest, admin: Admin, uow: Uow, clock: AppClock
) -> AdminDriver:
    return admin_driver_out(await RejectDriver(uow, clock)(admin.id, user_id, body.reason))


# ---------------------------------------------------------------- public profiles


@profiles_router.get(
    "/users/{user_id}/profile",
    summary="A user's public profile",
    description="First name, rating, completed trips, and (for approved drivers) their "
    "vehicle without its plate. Never their email or last name.",
    responses={
        **UNAUTHORIZED,
        **INVALID,
        404: _problem("No user with this ID", "user_not_found"),
    },
)
async def public_profile(user_id: UUID, user: AuthenticatedUser) -> PublicProfile:
    _not_implemented()


# ---------------------------------------------------------------- internal lookups


@internal_router.get(
    "/users",
    summary="Names, ratings and no-shows",
    description="For Trips (the driver's list of requests, auto-accept). No email.",
    responses=INVALID,
)
async def internal_users(ids: UserIds) -> InternalUsers:
    _not_implemented()


@internal_router.get(
    "/contacts",
    summary="Names and emails",
    description="For Notifications only: where to send emails.",
    responses=INVALID,
)
async def internal_contacts(ids: UserIds, uow: Uow) -> InternalContacts:
    users = await ListContacts(uow)(ids)
    return InternalContacts(
        contacts=[
            InternalContact(id=user.id, first_name=user.first_name, email=user.email.value)
            for user in users
        ]
    )
