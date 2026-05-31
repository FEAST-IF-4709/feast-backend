from django.core.management.base import BaseCommand
from apps.rbac.models import Permission, Role, RolePermission
from apps.tenants.models import Brand


PERMISSION_CATALOG = [
    # Brand & Outlet
    ("brand", "brand.view", "View brand info"),
    ("brand", "brand.update", "Update brand info"),
    ("outlet", "outlet.view", "View outlets"),
    ("outlet", "outlet.create", "Create outlet"),
    ("outlet", "outlet.update", "Update outlet"),
    ("outlet", "outlet.delete", "Delete outlet"),
    # Tables
    ("tables", "tables.view", "View tables"),
    ("tables", "tables.create", "Create table"),
    ("tables", "tables.update", "Update table / rotate QR"),
    ("tables", "tables.delete", "Delete table"),
    # RBAC
    ("rbac", "rbac.role.view", "View roles"),
    ("rbac", "rbac.role.create", "Create role"),
    ("rbac", "rbac.role.update", "Update role / assign permissions"),
    ("rbac", "rbac.role.delete", "Delete role"),
    # Staff
    ("staff", "staff.view", "View employees"),
    ("staff", "staff.create", "Create employee"),
    ("staff", "staff.update", "Update employee"),
    ("staff", "staff.delete", "Delete employee"),
    # Customer
    ("customer", "customer.view", "View customers"),
    # Catalog
    ("catalog", "products.view", "View brand products"),
    ("catalog", "products.create", "Create brand product"),
    ("catalog", "products.update", "Update brand product"),
    ("catalog", "products.delete", "Delete brand product"),
    ("catalog", "outlet_products.view", "View outlet products"),
    ("catalog", "outlet_products.create", "Create outlet product"),
    ("catalog", "outlet_products.update", "Update outlet product"),
    ("catalog", "outlet_products.delete", "Delete outlet product"),
    ("catalog", "categories.view", "View categories"),
    ("catalog", "categories.create", "Create category"),
    ("catalog", "categories.update", "Update category"),
    ("catalog", "categories.delete", "Delete category"),
    ("catalog", "promotions.view", "View promotions"),
    ("catalog", "promotions.create", "Create promotion"),
    ("catalog", "promotions.update", "Update promotion"),
    ("catalog", "promotions.delete", "Delete promotion"),
    # Orders
    ("orders", "orders.view", "View orders"),
    ("orders", "orders.create", "Create order"),
    ("orders", "orders.cancel", "Cancel order"),
    ("orders", "orders.refund", "Refund order"),
    # Cashier
    ("cashier", "cashier.order.create", "Cashier: create POS order"),
    ("cashier", "cashier.payment.settle_manual", "Cashier: manually settle payment"),
    # Kitchen
    ("kitchen", "kitchen.order.view", "Kitchen: view orders"),
    ("kitchen", "kitchen.order.update_status", "Kitchen: update order status"),
    ("kitchen", "kitchen.order.force_cancel", "Kitchen: force cancel order"),
    # Dashboard
    ("dashboard", "dashboard.view", "View dashboard"),
]

# Permissions per system role
ROLE_BASELINES = {
    "BRAND_OWNER": [p[1] for p in PERMISSION_CATALOG],
    "MANAGER": [
        p[1] for p in PERMISSION_CATALOG
        if p[1] not in {
            "rbac.role.create", "rbac.role.update", "rbac.role.delete",
            "staff.delete",
            "brand.update",
        }
    ],
    "CASHIER": [
        "outlet.view",
        "tables.view",
        "products.view",
        "outlet_products.view",
        "customer.view",
        "orders.view",
        "orders.create",
        "orders.cancel",
        "cashier.order.create",
        "cashier.payment.settle_manual",
    ],
    "KITCHEN": [
        "outlet.view",
        "orders.view",
        "kitchen.order.view",
        "kitchen.order.update_status",
    ],
}


class Command(BaseCommand):
    help = "Seed Permission catalog and system roles for all existing brands."

    def handle(self, *args, **kwargs):
        self.stdout.write("Syncing permissions...")
        perm_map = {}
        for module, codename, description in PERMISSION_CATALOG:
            perm, created = Permission.objects.update_or_create(
                codename=codename,
                defaults={"module": module, "description": description},
            )
            perm_map[codename] = perm
            if created:
                self.stdout.write(f"  + {codename}")

        self.stdout.write(f"Total permissions: {len(perm_map)}")

        brands = Brand.objects.all()
        if not brands.exists():
            self.stdout.write(self.style.WARNING("No brands found — system roles will be seeded when brands are created."))
            return

        for brand in brands:
            self.stdout.write(f"\nSeeding system roles for brand: {brand.name}")
            for role_name, codenames in ROLE_BASELINES.items():
                role, _ = Role.objects.get_or_create(
                    brand=brand,
                    name=role_name,
                    defaults={"is_system": True},
                )
                role.is_system = True
                role.save(update_fields=["is_system"])

                existing_codes = set(
                    role.rolepermissions.values_list("permission__codename", flat=True)
                )
                to_add = [
                    RolePermission(role=role, permission=perm_map[code])
                    for code in codenames
                    if code in perm_map and code not in existing_codes
                ]
                if to_add:
                    RolePermission.objects.bulk_create(to_add, ignore_conflicts=True)
                self.stdout.write(f"  {role_name}: {len(codenames)} permissions")

        self.stdout.write(self.style.SUCCESS("\nPermission seed complete."))
