# agents/consent.py
"""
Consent & Authorization gate for patient-specific data access.

Before any agent tool reads patient records, the orchestrator calls
check_patient_data_consent() to verify that the caller is authorized
and the patient (or their representative) has granted appropriate scope.

Minimal API — production implementations should integrate with the
organization's consent management system (e.g. SMART-on-FHIR scopes,
OAuth2 token introspection, or an internal consent registry).
"""
from dataclasses import dataclass, field
from typing import List, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

ALL_SCOPES = [
    "patient:read",
    "medication:read",
    "lab:read",
    "procedure:read",
    "condition:read",
    "allergy:read",
    "encounter:read",
    "careplan:read",
    "action:write",
]


@dataclass
class ConsentResult:
    """Result of a consent / authorization check."""
    authorized: bool
    scopes: List[str] = field(default_factory=list)
    patient_id: Optional[str] = None
    reason: str = ""


async def check_patient_data_consent(
    patient_id: str,
    practitioner_id: Optional[str] = None,
    required_scopes: Optional[List[str]] = None,
) -> ConsentResult:
    """
    Verify that the current request is authorized to access patient data.

    In production this would:
      1. Validate the caller's OAuth2/SMART-on-FHIR token.
      2. Look up the patient's consent record (opt-in / opt-out / scope-limited).
      3. Intersect granted scopes with ``required_scopes``.

    Current implementation: returns authorized=True with full scopes when
    a valid patient_id is provided.  Replace the body with real integration.

    Args:
        patient_id: The patient whose data will be accessed.
        practitioner_id: The practitioner making the request (if applicable).
        required_scopes: Specific scopes the caller needs (e.g. ["lab:read"]).
                         If None, all scopes are requested.

    Returns:
        ConsentResult with authorization decision and granted scopes.
    """
    if not patient_id:
        return ConsentResult(
            authorized=False,
            scopes=[],
            patient_id=patient_id,
            reason="No patient_id provided; cannot authorize patient data access.",
        )

    # --- placeholder: replace with real consent lookup ---
    granted_scopes = list(ALL_SCOPES)
    if required_scopes:
        missing = set(required_scopes) - set(granted_scopes)
        if missing:
            logger.warning(
                "Consent check: scopes %s not granted for patient %s",
                missing, patient_id,
            )
            return ConsentResult(
                authorized=False,
                scopes=[s for s in granted_scopes if s not in missing],
                patient_id=patient_id,
                reason=f"Missing required scopes: {sorted(missing)}",
            )

    logger.info("Consent granted for patient %s (scopes: %s)", patient_id, granted_scopes)
    return ConsentResult(
        authorized=True,
        scopes=granted_scopes,
        patient_id=patient_id,
        reason="Consent verified.",
    )
