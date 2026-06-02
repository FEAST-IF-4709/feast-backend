from django.db.models.signals import post_save
from django.dispatch import receiver


SYSTEM_ROLE_PERMISSIONS = {
    "BRAND_OWNER": None,  # None = all permissions
    "MANAGER": {
        "rbac.role.create", "rbac.role.update", "rbac.role.delete",
        "staff.delete",
        "brand.update",
    },  # excluded set
    "CASHIER": [
        "outlet.view", "tables.view", "products.view", "outlet_products.view",
        "customer.view", "orders.view", "orders.create", "orders.cancel",
        "cashier.order.create", "cashier.payment.settle_manual",
    ],
    "KITCHEN": [
        "outlet.view", "orders.view",
        "kitchen.order.view", "kitchen.order.update_status",
    ],
}

# Lower number = higher authority in the hierarchy.
SYSTEM_ROLE_RANKS = {
    "BRAND_OWNER": 1,
    "MANAGER": 2,
    "CASHIER": 3,
    "KITCHEN": 3,
}


@receiver(post_save, sender="tenants.Brand")
def seed_system_roles_for_new_brand(sender, instance, created, **kwargs):
    if not created:
        return

    from apps.rbac.models import Permission, Role, RolePermission

    all_perms = {p.codename: p for p in Permission.objects.all()}
    if not all_perms:
        return

    for role_name, perm_spec in SYSTEM_ROLE_PERMISSIONS.items():
        role, _ = Role.objects.get_or_create(
            brand=instance,
            name=role_name,
            defaults={"is_system": True, "rank": SYSTEM_ROLE_RANKS.get(role_name)},
        )
        role.is_system = True
        role.rank = SYSTEM_ROLE_RANKS.get(role_name)
        role.save(update_fields=["is_system", "rank"])

        if perm_spec is None:
            codenames = list(all_perms.keys())
        elif isinstance(perm_spec, set):
            codenames = [c for c in all_perms if c not in perm_spec]
        else:
            codenames = list(perm_spec)

        existing = set(role.rolepermissions.values_list("permission__codename", flat=True))
        to_add = [
            RolePermission(role=role, permission=all_perms[c])
            for c in codenames
            if c in all_perms and c not in existing
        ]
        if to_add:
            RolePermission.objects.bulk_create(to_add, ignore_conflicts=True)
