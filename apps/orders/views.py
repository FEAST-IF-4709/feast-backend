from django.shortcuts import render
from apps.users.permissions import CheckPermission
from rest_framework import viewsets, permissions
from .serializers import RoleSerializer
from .models import Role
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    def get_permissions(self):
        # Pemetaan aksi ke codename permission
        mapping = {
            'list': 'orders.view',
            'retrieve': 'orders.view',
            'create': 'orders.create',
            'update': 'orders.update',
            'partial_update': 'orders.update',
            'destroy': 'orders.delete',
        }
        
        codename = mapping.get(self.action)
        if codename:
            return [CheckPermission(codename)()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        employee = user.employee_profile
        
        # Ambil queryset dasar
        qs = self.queryset.filter(outlet__brand=employee.brand)
        
        # Jika dia bukan 'Owner' atau 'Regional Manager', 
        # batasi hanya bisa lihat data di outlet tempat dia kerja saja
        if employee.role.name != 'Brand Owner':
            qs = qs.filter(outlet=employee.outlet)
            
        return qs