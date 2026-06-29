"""FCM push notification service for order status changes."""
import logging

logger = logging.getLogger(__name__)

_STATUS_BODY = {
    "RECEIVED": "Pesanan diterima oleh dapur! 🍽️",
    "IN_PROGRESS": "Pesananmu sedang dimasak... 👨‍🍳",
    "READY": "Pesananmu siap! Segera disajikan. ✅",
    "SERVED": "Selamat menikmati! 😋",
    "COMPLETED": "Terima kasih sudah memesan! ⭐",
    "CANCELLED": "Pesananmu telah dibatalkan.",
}


def _get_firebase_app():
    try:
        import firebase_admin
        from firebase_admin import credentials
        import os

        app_name = "feast_push"
        try:
            return firebase_admin.get_app(app_name)
        except ValueError:
            pass

        cred_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "")
        if not cred_path:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_PATH not set; push notifications disabled.")
            return None
        cred = credentials.Certificate(cred_path)
        return firebase_admin.initialize_app(cred, name=app_name)
    except Exception as exc:
        logger.warning("Firebase init failed: %s", exc)
        return None


def send_order_status_push(order_id: str, order_number: str, customer_user_id: int, new_status: str) -> None:
    """Send FCM push notification to all devices belonging to customer_user_id."""
    body = _STATUS_BODY.get(new_status)
    if not body:
        return

    from apps.authentication.models import DeviceToken
    tokens = list(DeviceToken.objects.filter(user_id=customer_user_id).values_list("token", flat=True))
    if not tokens:
        return

    app = _get_firebase_app()
    if app is None:
        return

    try:
        from firebase_admin import messaging

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=f"Pesanan #{order_number}",
                body=body,
            ),
            data={
                "order_id": order_id,
                "fulfillment_status": new_status,
                "type": "order_status",
            },
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default"),
                ),
            ),
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message, app=app)

        # Clean up invalid tokens
        if response.failure_count > 0:
            invalid_tokens = [
                tokens[i]
                for i, r in enumerate(response.responses)
                if not r.success
            ]
            if invalid_tokens:
                DeviceToken.objects.filter(token__in=invalid_tokens).delete()
                logger.info("Removed %d invalid FCM tokens.", len(invalid_tokens))

    except Exception as exc:
        logger.error("FCM send failed for order %s: %s", order_id, exc)


def send_brand_broadcast_push(brand_id: int, title: str, body: str) -> int:
    """Send a broadcast push notification to all customers who have ordered from brand_id.

    Returns the number of successful sends (best-effort; 0 on any setup failure).
    """
    from apps.authentication.models import DeviceToken
    from apps.orders.models import Order

    customer_ids = list(
        Order.objects
        .filter(outlet__brand_id=brand_id)
        .values_list("customer_id", flat=True)
        .distinct()
    )
    customer_id_strs = [str(cid) for cid in customer_ids]
    tokens = list(
        DeviceToken.objects
        .filter(user_id__in=customer_id_strs)
        .values_list("token", flat=True)
    )
    if not tokens:
        return 0

    app = _get_firebase_app()
    if app is None:
        return 0

    try:
        from firebase_admin import messaging

        # FCM allows max 500 tokens per multicast call — chunk if needed.
        chunk_size = 500
        success_count = 0
        invalid_tokens = []

        for i in range(0, len(tokens), chunk_size):
            chunk = tokens[i : i + chunk_size]
            msg = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data={"type": "brand_broadcast"},
                android=messaging.AndroidConfig(priority="high"),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))
                ),
                tokens=chunk,
            )
            response = messaging.send_each_for_multicast(msg, app=app)
            success_count += response.success_count
            invalid_tokens += [
                chunk[j]
                for j, r in enumerate(response.responses)
                if not r.success
            ]

        if invalid_tokens:
            DeviceToken.objects.filter(token__in=invalid_tokens).delete()
            logger.info("Removed %d invalid FCM tokens after broadcast.", len(invalid_tokens))

        return success_count
    except Exception as exc:
        logger.error("FCM broadcast failed for brand %s: %s", brand_id, exc)
        return 0
