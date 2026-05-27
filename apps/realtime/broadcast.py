from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def _send(group_name: str, event_type: str, payload: dict):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {"type": event_type.replace(".", "_"), "payload": payload},
    )


def broadcast_to_kitchen(outlet_id: str, event_type: str, payload: dict):
    _send(f"outlet.{outlet_id}.kitchen", event_type, payload)


def broadcast_to_order(order_id: str, event_type: str, payload: dict):
    _send(f"order.{order_id}", event_type, payload)


def broadcast_to_dashboard(outlet_id: str, event_type: str, payload: dict):
    _send(f"outlet.{outlet_id}.dashboard", event_type, payload)
