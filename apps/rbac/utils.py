from __future__ import annotations


def seed_roles_for_brand(brand):
    """
    Idempotent — create/update the 4 system roles for a brand and assign their permissions.
    Safe to call multiple times (uses get_or_create + bulk_create ignore_conflicts).
    Called automatically when a new brand is created via the SuperAdmin API.
    """
    from apps.rbac.models import Permission, Role, RolePermission
    from apps.rbac.management.commands.seed_permissions import PERMISSION_CATALOG, ROLE_BASELINES, ROLE_RANKS

    all_codenames = [p[1] for p in PERMISSION_CATALOG]
    perm_objs = {p.codename: p for p in Permission.objects.filter(codename__in=all_codenames)}

    for role_name, codenames in ROLE_BASELINES.items():
        role, _ = Role.objects.get_or_create(
            brand=brand,
            name=role_name,
            defaults={"is_system": True, "rank": ROLE_RANKS.get(role_name)},
        )
        role.is_system = True
        role.rank = ROLE_RANKS.get(role_name)
        role.save(update_fields=["is_system", "rank"])

        existing = set(role.rolepermissions.values_list("permission__codename", flat=True))
        to_add = [
            RolePermission(role=role, permission=perm_objs[code])
            for code in codenames
            if code in perm_objs and code not in existing
        ]
        if to_add:
            RolePermission.objects.bulk_create(to_add, ignore_conflicts=True)


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
