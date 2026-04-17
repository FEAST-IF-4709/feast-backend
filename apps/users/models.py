import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# Create your models here.

# User manager (logic buat bikin akun)
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email wajib diisi!!')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        # Jika terdapat password maka employee
        
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
            
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'EMPLOYEE')
        extra_fields.setdefault('auth_provider', 'EMAIL')

        return self.create_user(email, password, **extra_fields)
    
    
# Base User
class BaseUser(AbstractBaseUser, PermissionsMixin):
    class UserType(models.TextChoices):
        EMPLOYEE = 'EMPLOYEE', 'Employee'
        CUSTOMER = 'CUSTOMER',  'Customer'
        
    class AuthProvider(models.TextChoices):
        EMAIL = 'EMAIL', 'Email & Password'
        GOOGLE = 'GOOGLE', 'Google OAuth'
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, max_length=225)
    
    # Kategori User
    user_type = models.CharField(max_length=20, choices=UserType.choices)
    auth_provider = models.CharField(max_length=20, choices=AuthProvider.choices)
    
    # Buat Django Admin
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False) # True kalo boleh akses panel admin bawaan Django
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] # Tidak ada tambahan field wajib saat superuser dibuat selain email & password

    def __str__(self):
        return f"{self.email} ({self.user_type})"
    


# RBAC
class Permission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    
    def __str__(self):
        return self.name
    
class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    brand = models.ForeignKey('tenants.Brand', on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=100)
    
    permission = models.ManyToManyField(Permission, blank=True)
    
    def __str__(self):
        return f"{self.name} - {self.brand.name}"
    


class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(BaseUser, on_delete=models.CASCADE, related_name='employee_profile')
    name = name = models.CharField(max_length=255)
    
    brand = models.ForeignKey('tenants.Brand', on_delete=models.CASCADE, related_name='employees')
    outlet = models.ForeignKey('tenants.Outlet', on_delete=models.SET_NULL, related_name='employees', null=True)
    
    role = models.ForeignKey('Role', on_delete=models.RESTRICT)
    pin_code = models.CharField(max_length=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.outlet.name} - {self.brand.name}" 
    
class Customer(models.Model):
    class Tier(models.TextChoices):
        BRONZE = 'BRONZE', 'Bronze'
        SILVER = 'SILVER', 'Silver'
        GOLD = 'GOLD', 'Gold'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(BaseUser, on_delete=models.CASCADE, related_name='customer_profile')
    
    name = models.CharField(max_length=255)
    
    # Nullable karena konsep "Progressive Profiling" saat login Google pertama kali
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True) 
    
    points = models.IntegerField(default=0)
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.BRONZE)

    def __str__(self):
        return f"{self.name} (Customer)"