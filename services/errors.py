"""Public service exceptions re-exported without creating new definitions."""

from services.career_service import UserNotFoundError, CareerNotFoundError
from services.opportunity_service import OpportunityNotFoundError
from services.application_service import (
    ApplicationNotFoundError, InvalidApplicationStatusError, ApplicationNotRemovableError,
)

__all__ = [
    "UserNotFoundError", "CareerNotFoundError", "OpportunityNotFoundError",
    "ApplicationNotFoundError", "InvalidApplicationStatusError", "ApplicationNotRemovableError",
]
