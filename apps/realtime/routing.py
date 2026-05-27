from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/kitchen/(?P<outlet_id>[^/]+)/$", consumers.KitchenConsumer.as_asgi()),
    re_path(r"ws/order/(?P<order_id>[^/]+)/$", consumers.OrderConsumer.as_asgi()),
]
