from __future__ import annotations


def get_requester_rank(request) -> int | None:
    """Returns the rank of the requesting user's role.

    Tries JWT claim first. Falls back to a DB lookup for tokens issued
    before the role_rank claim was added.
    """
    from apps.rbac.models import Role

    tenant = getattr(request, "tenant", None) or {}
    rank = tenant.get("role_rank")
    if rank is not None:
        return rank
    role_id = tenant.get("role_id")
    if role_id:
        return Role.objects.values_list("rank", flat=True).filter(id=role_id).first()
    return None


def can_modify_role(request, target_role) -> bool:
    """True if the requester has hierarchy authority to modify target_role.

    Custom roles (is_system=False) are always modifiable.
    BRAND_OWNER (rank=1) can modify any system role.
    Other ranks can only modify roles with a strictly higher rank number.
    """
    if not target_role.is_system:
        return True
    requester_rank = get_requester_rank(request)
    if requester_rank is None or target_role.rank is None:
        return False
    if requester_rank == 1:
        return True
    return requester_rank < target_role.rank
