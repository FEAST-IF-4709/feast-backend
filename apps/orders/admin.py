from django.contrib import admin
from apps.orders.models import Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["line_total"]


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ["changed_at"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "outlet", "order_source", "payment_status", "fulfillment_status", "grand_total", "placed_at"]
    list_filter = ["order_source", "payment_status", "fulfillment_status", "outlet"]
    search_fields = ["order_number", "customer__full_name", "customer__phone"]
    readonly_fields = ["id", "order_number", "placed_at"]
    inlines = [OrderItemInline, OrderStatusHistoryInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["order", "quantity", "unit_price", "line_total"]
    search_fields = ["order__order_number"]
    readonly_fields = ["line_total"]
