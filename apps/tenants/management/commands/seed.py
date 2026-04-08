import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.tenants.models import Brand, Outlet
from apps.users.models import Role, Employee
from apps.catalog.models import Category, Product
from apps.orders.models import Order, OrderItem

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed the database with initial dummy data for FEAST Dashboard'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Memulai proses seeding database...'))

        # 1. BUAT BRAND & OUTLET
        brand, created = Brand.objects.get_or_create(name='Kopi Senja Nusantara')
        
        outlet_jkt, _ = Outlet.objects.get_or_create(
            brand=brand, 
            name='Kopi Senja - Sudirman', 
            defaults={'address': 'Jl. Jendral Sudirman No. 1, Jakarta', 'is_active': True}
        )
        outlet_bdg, _ = Outlet.objects.get_or_create(
            brand=brand, 
            name='Kopi Senja - Braga', 
            defaults={'address': 'Jl. Braga No. 99, Bandung', 'is_active': True}
        )

        # 2. BUAT ROLE (JABATAN)
        role_manager, _ = Role.objects.get_or_create(brand=brand, name='Store Manager')
        role_cashier, _ = Role.objects.get_or_create(brand=brand, name='Cashier')

        # 3. BUAT USER (KARYAWAN)
        email_kasir = 'kasir.sudirman@kopisenja.com'
        if not User.objects.filter(email=email_kasir).exists():
            user_kasir = User.objects.create_user(
                email=email_kasir, 
                password='password123',
                user_type='EMPLOYEE',
                is_staff=True # Supaya bisa login admin kalau butuh
            )
            Employee.objects.create(
                user=user_kasir, brand=brand, outlet=outlet_jkt, role=role_cashier
            )

        # 4. BUAT KATEGORI & MENU
        cat_coffee, _ = Category.objects.get_or_create(brand=brand, name='Coffee')
        cat_snack, _ = Category.objects.get_or_create(brand=brand, name='Snacks')

        products_data = [
            (cat_coffee, 'Kopi Susu Gula Aren', '25000.00'),
            (cat_coffee, 'Americano Cold', '20000.00'),
            (cat_coffee, 'Caramel Macchiato', '35000.00'),
            (cat_snack, 'Croissant Butter', '28000.00'),
            (cat_snack, 'French Fries', '22000.00'),
        ]

        products = []
        for cat, name, price in products_data:
            prod, _ = Product.objects.get_or_create(
                brand=brand, category=cat, name=name,
                defaults={'price': Decimal(price), 'is_available': True}
            )
            products.append(prod)

        # 5. BUAT TRANSAKSI (ORDERS)
        # Kita buat 5 transaksi dummy agar chart di React nanti ada isinya
        kasir = Employee.objects.filter(role=role_cashier).first()
        
        # Hapus order lama agar tidak menumpuk saat di-seed ulang
        Order.objects.all().delete() 

        order_types = ['DINE_IN', 'TAKEAWAY']
        statuses = ['COMPLETED', 'PENDING']
        payment_methods = ['CASH', 'QRIS', 'CARD']

        for i in range(1, 6):
            order = Order.objects.create(
                outlet=outlet_jkt,
                cashier=kasir,
                customer_name=f'Pelanggan {i}',
                order_type=random.choice(order_types),
                status=random.choice(statuses),
                payment_status='PAID',
                payment_method=random.choice(payment_methods),
            )

            # Masukkan 1-3 menu random ke dalam pesanan ini
            num_items = random.randint(1, 3)
            selected_products = random.sample(products, num_items)
            
            subtotal = Decimal('0.00')
            for prod in selected_products:
                qty = random.randint(1, 2)
                price = prod.price
                OrderItem.objects.create(
                    order=order, product=prod, quantity=qty, price_at_time=price
                )
                subtotal += (price * qty)
            
            # Update total di struk
            tax = subtotal * Decimal('0.11') # PPN 11%
            order.subtotal = subtotal
            order.tax = tax
            order.total_amount = subtotal + tax
            order.save()

        self.stdout.write(self.style.SUCCESS('✨ Berhasil! Data dummy FEAST telah berhasil di-seed.'))