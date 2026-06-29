from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError

FULFILLMENT_TRANSITIONS: dict[str, list[str]] = {
    "RECEIVED": ["IN_PROGRESS", "CANCELLED"],
    "IN_PROGRESS": ["READY", "CANCELLED"],
    "READY": ["SERVED", "COMPLETED"],   # shortcut: skip SERVED untuk order delivery/takeaway
    "SERVED": ["COMPLETED"],
    "COMPLETED": [],
    "CANCELLED": [],
}

# Transitions that require an explicit permission codename beyond the default actor check
TRANSITION_REQUIRED_PERMISSIONS: dict[tuple[str, str], str] = {
    ("IN_PROGRESS", "CANCELLED"): "kitchen.order.force_cancel",
}


def validate_transition(
    from_status: str,
    to_status: str,
    actor_permissions: frozenset[str] = frozenset(),
) -> None:
    """Validate a fulfillment status transition and the actor's permission to perform it.

    Raises ValidationError(code='STATE_TRANSITION_INVALID') if the path is not in the
    allowed graph.  Raises PermissionDenied if the transition requires an explicit
    permission codename that the actor does not hold.
    """
    allowed = FULFILLMENT_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise ValidationError(
            f"Transisi '{from_status}' → '{to_status}' tidak valid. Allowed: {allowed}",
            code="STATE_TRANSITION_INVALID",
        )
    required_perm = TRANSITION_REQUIRED_PERMISSIONS.get((from_status, to_status))
    if required_perm and required_perm not in actor_permissions:
        raise PermissionDenied(f"Requires permission '{required_perm}'.")
