from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


def _ws_event(event_name: str, data: dict) -> dict:
    return {"success": True, "code": "OK", "event": event_name, "data": data}


class KitchenConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        outlet_id = self.scope["url_route"]["kwargs"]["outlet_id"]
        tenant = self.scope.get("tenant")

        if not tenant or "kitchen.order.view" not in tenant["permissions"]:
            await self.close(code=4403)
            return

        if str(outlet_id) not in [str(o) for o in tenant.get("outlet_ids", [])]:
            await self.close(code=4403)
            return

        self.group_name = f"outlet.{outlet_id}.kitchen"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def order_created(self, event):
        await self.send_json(_ws_event("order.created", event["payload"]))

    async def order_status_changed(self, event):
        await self.send_json(_ws_event("order.status_changed", event["payload"]))

    async def order_cancelled(self, event):
        await self.send_json(_ws_event("order.cancelled", event["payload"]))


class OrderConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        order_id = self.scope["url_route"]["kwargs"]["order_id"]
        user = self.scope.get("user")
        tenant = self.scope.get("tenant")

        if not user:
            await self.close(code=4401)
            return

        actor_type = (tenant or {}).get("actor_type")

        if actor_type == "CUSTOMER":
            allowed = await self._customer_owns_order(user, order_id)
        elif actor_type == "EMPLOYEE":
            allowed = await self._employee_can_access_order(tenant, order_id)
        else:
            allowed = False

        if not allowed:
            await self.close(code=4403)
            return

        self.group_name = f"order.{order_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def _customer_owns_order(self, user, order_id):
        from apps.orders.models import Order
        return Order.objects.filter(pk=order_id, customer=user).exists()

    @database_sync_to_async
    def _employee_can_access_order(self, tenant, order_id):
        from apps.orders.models import Order
        return Order.objects.filter(
            pk=order_id,
            brand_id=tenant["brand_id"],
            outlet_id__in=tenant["outlet_ids"],
        ).exists()

    async def payment_status_changed(self, event):
        await self.send_json(_ws_event("payment.status_changed", event["payload"]))

    async def fulfillment_status_changed(self, event):
        await self.send_json(_ws_event("fulfillment.status_changed", event["payload"]))


class DashboardConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        outlet_id = self.scope["url_route"]["kwargs"]["outlet_id"]
        tenant = self.scope.get("tenant")

        if not tenant or "kitchen.order.view" not in tenant["permissions"]:
            await self.close(code=4403)
            return

        if str(outlet_id) not in [str(o) for o in tenant.get("outlet_ids", [])]:
            await self.close(code=4403)
            return

        self.group_name = f"outlet.{outlet_id}.dashboard"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def order_created(self, event):
        await self.send_json(_ws_event("order.created", event["payload"]))

    async def order_status_changed(self, event):
        await self.send_json(_ws_event("order.status_changed", event["payload"]))

    async def order_cancelled(self, event):
        await self.send_json(_ws_event("order.cancelled", event["payload"]))

    async def payment_status_changed(self, event):
        await self.send_json(_ws_event("payment.status_changed", event["payload"]))
