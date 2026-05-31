from decimal import Decimal
from django.core.management.base import BaseCommand

from apps.tenants.models import Brand, Outlet
from apps.rbac.models import Role
from apps.staff.models import Employee
from apps.customers.models import Customer
from apps.catalog.models import Category, BrandProduct, OutletProduct


class Command(BaseCommand):
    help = "Seed database with initial dummy data for FEAST development."

    def handle(self, *args, **options):
        self.stdout.write("Seeding FEAST database...")

        # 1. Brand
        brand, _ = Brand.objects.get_or_create(
            slug="kopi-senja",
            defaults={
                "name": "Kopi Senja Nusantara",
                "owner_email": "owner@kopisenja.com",
                "subscription_status": Brand.SubscriptionStatus.TRIAL,
                "is_active": True,
            },
        )
        self.stdout.write(f"Brand: {brand.name}")

        # 2. Outlets
        outlet_jkt, _ = Outlet.objects.get_or_create(
            brand=brand,
            name="Kopi Senja - Sudirman",
            defaults={
                "address": "Jl. Jendral Sudirman No. 1, Jakarta",
                "latitude": Decimal("-6.208763"),
                "longitude": Decimal("106.845599"),
                "is_active": True,
            },
        )
        outlet_bdg, _ = Outlet.objects.get_or_create(
            brand=brand,
            name="Kopi Senja - Braga",
            defaults={
                "address": "Jl. Braga No. 99, Bandung",
                "latitude": Decimal("-6.916530"),
                "longitude": Decimal("107.609630"),
                "is_active": True,
            },
        )
        self.stdout.write(f"Outlets: {outlet_jkt.name}, {outlet_bdg.name}")

        # 3. System roles (seeded by seed_permissions, but ensure they exist)
        role_owner, _ = Role.objects.get_or_create(
            brand=brand, name="BRAND_OWNER", defaults={"is_system": True}
        )
        role_cashier, _ = Role.objects.get_or_create(
            brand=brand, name="CASHIER", defaults={"is_system": True}
        )
        Role.objects.get_or_create(brand=brand, name="KITCHEN", defaults={"is_system": True})
        Role.objects.get_or_create(brand=brand, name="MANAGER", defaults={"is_system": True})
        self.stdout.write("Roles ensured.")

        # 4. Employees
        owner_email = "owner@kopisenja.com"
        if not Employee.objects.filter(brand=brand, email=owner_email).exists():
            owner = Employee(
                brand=brand,
                outlet=None,
                role=role_owner,
                email=owner_email,
                full_name="Owner Kopi Senja",
                is_active=True,
            )
            owner.set_password("password123")
            owner.save()
            self.stdout.write(f"Employee created: {owner_email}")

        kasir_email = "kasir.sudirman@kopisenja.com"
        if not Employee.objects.filter(brand=brand, email=kasir_email).exists():
            kasir = Employee(
                brand=brand,
                outlet=outlet_jkt,
                role=role_cashier,
                email=kasir_email,
                full_name="Kasir Sudirman",
                is_active=True,
            )
            kasir.set_password("password123")
            kasir.save()
            self.stdout.write(f"Employee created: {kasir_email}")

        # 5. Customer
        if not Customer.objects.filter(phone="08123456789").exists():
            customer = Customer(
                phone="08123456789",
                email="budi@gmail.com",
                full_name="Budi Santoso",
                is_active=True,
            )
            customer.set_password("password123")
            customer.save()
            self.stdout.write("Customer created: Budi Santoso")

        # 6. Catalog
        cat_coffee, _ = Category.objects.get_or_create(brand=brand, name="Coffee")
        cat_snack, _ = Category.objects.get_or_create(brand=brand, name="Snacks")

        products_data = [
            (cat_coffee, "Kopi Susu Gula Aren", "25000.00"),
            (cat_coffee, "Americano Cold", "20000.00"),
            (cat_coffee, "Caramel Macchiato", "35000.00"),
            (cat_snack, "Croissant Butter", "28000.00"),
            (cat_snack, "French Fries", "22000.00"),
        ]

        brand_products = []
        for cat, name, price in products_data:
            bp, _ = BrandProduct.objects.get_or_create(
                brand=brand,
                name=name,
                defaults={"category": cat, "base_price": Decimal(price), "is_active": True},
            )
            brand_products.append(bp)

        for bp in brand_products:
            OutletProduct.objects.get_or_create(
                brand_product=bp,
                outlet=outlet_jkt,
                defaults={"stock_available": True},
            )

        self.stdout.write(f"Catalog: {len(brand_products)} products seeded.")
        self.stdout.write(self.style.SUCCESS("\nSeed complete! Login: kasir.sudirman@kopisenja.com / password123"))
