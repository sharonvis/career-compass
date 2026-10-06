"""Public service exceptions re-exported without creating new definitions."""

from services.career_service import UserNotFoundError, CareerNotFoundError
from services.opportunity_service import OpportunityNotFoundError
from services.application_service import (
    ApplicationNotFoundError, InvalidApplicationStatusError, ApplicationNotRemovableError,
)

class SkillNotFoundError(LookupError):
    """The requested catalog skill does not exist."""


class EvidenceNotFoundError(LookupError):
    """No evidence is available to this user for the requested ID."""


__all__ = [
    "UserNotFoundError", "CareerNotFoundError", "OpportunityNotFoundError",
    "ApplicationNotFoundError", "InvalidApplicationStatusError", "ApplicationNotRemovableError",
    "SkillNotFoundError", "EvidenceNotFoundError",
]
