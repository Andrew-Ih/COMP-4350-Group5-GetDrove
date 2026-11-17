"""A student's application to drive (#8): their documents, their vehicle, and where the
admin's decision stands.

Every account can ride. Posting trips needs an approved application:

    none ──upload documents──▶ pending ──admin approves──▶ approved
                                  ▲    └──admin rejects──▶ rejected
                                  └────upload again────────┘

An approved driver can't upload again, and only a pending application can be decided.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID

from accounts.domain.errors import (
    DriverAlreadyApprovedError,
    DriverNotPendingError,
    VehicleMissingError,
)
from common_web import InvalidField, InvalidInputError

VEHICLE_FIELD_LENGTH = range(1, 31)
_PLATE = re.compile(r"[A-Z0-9]{2,8}")
REJECTION_REASON_LENGTH = range(1, 501)


class DriverStatus(StrEnum):
    NONE = "none"  # never uploaded documents
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Vehicle:
    make: str
    model: str
    colour: str
    plate: str  # uppercase; only the driver, admins and their accepted riders see it

    @classmethod
    def create(cls, make: str, model: str, colour: str, plate: str) -> Self:
        """Trims every field and uppercases the plate. Any invalid field is 422
        invalid_input, naming each one."""
        values = {"make": make.strip(), "model": model.strip(), "colour": colour.strip()}
        normalized_plate = plate.strip().upper()
        errors = [
            InvalidField(field, "Use 1 to 30 characters")
            for field, value in values.items()
            if len(value) not in VEHICLE_FIELD_LENGTH
        ]
        if not _PLATE.fullmatch(normalized_plate):
            errors.append(InvalidField("plate", "Use 2 to 8 letters and numbers"))
        if errors:
            raise InvalidInputError("Check your vehicle details.", errors)
        return cls(plate=normalized_plate, **values)


@dataclass
class DriverProfile:
    user_id: UUID
    status: DriverStatus = DriverStatus.NONE
    # Where DocumentStorage keeps each file (#9); the files themselves are never in the
    # database, and these keys never leave Accounts.
    licence_key: str | None = None
    insurance_key: str | None = None
    vehicle: Vehicle | None = None
    submitted_at: datetime | None = None  # when documents were last uploaded
    reviewed_at: datetime | None = None  # when an admin last decided
    reviewed_by: UUID | None = None  # that admin
    rejection_reason: str | None = None  # set while rejected

    @property
    def is_approved(self) -> bool:
        return self.status is DriverStatus.APPROVED

    def submit_documents(self, licence_key: str, insurance_key: str, now: datetime) -> None:
        """New documents (#9): the application waits for an admin again. 409
        driver_already_approved once approved."""
        if self.is_approved:
            raise DriverAlreadyApprovedError("You're already approved to drive.")
        self.licence_key = licence_key
        self.insurance_key = insurance_key
        self.submitted_at = now
        self.status = DriverStatus.PENDING
        self.rejection_reason = None

    def save_vehicle(self, vehicle: Vehicle) -> None:
        """Saving or changing the vehicle (#125) is allowed at any status and doesn't need
        a new review: the documents are what the admin checks."""
        self.vehicle = vehicle

    def approve(self, admin_id: UUID, now: datetime) -> None:
        """409 driver_not_pending unless it's waiting for a decision, and 409 vehicle_missing
        without a vehicle: riders need it to find their driver."""
        self._check_pending()
        if self.vehicle is None:
            raise VehicleMissingError("The driver hasn't saved their vehicle yet.")
        self.status = DriverStatus.APPROVED
        self._decided(admin_id, now)

    def reject(self, admin_id: UUID, reason: str, now: datetime) -> None:
        """The reason is shown to the driver, who can upload new documents."""
        reason = reason.strip()
        if len(reason) not in REJECTION_REASON_LENGTH:
            raise InvalidInputError(
                "Say why, so the driver knows what to fix.",
                [InvalidField("reason", "Use 1 to 500 characters")],
            )
        self._check_pending()
        self.status = DriverStatus.REJECTED
        self._decided(admin_id, now)
        self.rejection_reason = reason

    def _check_pending(self) -> None:
        if self.status is not DriverStatus.PENDING:
            raise DriverNotPendingError(f"This application is {self.status.value}, not pending.")

    def _decided(self, admin_id: UUID, now: datetime) -> None:
        self.reviewed_at = now
        self.reviewed_by = admin_id
        self.rejection_reason = None
