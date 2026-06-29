import math
from datetime import timedelta

from django.db import models
from django.utils import timezone


def _tier_window_start():
    """Returns the first day of the previous calendar month (UTC date)."""
    today = timezone.now().date()
    first_of_this_month = today.replace(day=1)
    last_of_prev_month = first_of_this_month - timedelta(days=1)
    return last_of_prev_month.replace(day=1)


def compute_tier(earn_pts_in_window: int) -> str:
    from apps.customers.models import LoyaltyAccount
    if earn_pts_in_window >= 200:
        return LoyaltyAccount.TierLevel.GOLD
    elif earn_pts_in_window >= 100:
        return LoyaltyAccount.TierLevel.SILVER
    return LoyaltyAccount.TierLevel.BRONZE


def get_tier_points_in_window(account) -> int:
    from apps.customers.models import LoyaltyTransaction
    window_start = _tier_window_start()
    result = (
        account.transactions
        .filter(txn_type=LoyaltyTransaction.TxnType.EARN, created_at__date__gte=window_start)
        .aggregate(total=models.Sum("points"))["total"]
    )
    return result or 0


def recompute_and_save_tier(account) -> int:
    """
    Recomputes tier based on EARN points in current window and saves if changed.
    Must be called while account row is already locked via select_for_update().
    Returns tier_points_in_window.
    """
    pts = get_tier_points_in_window(account)
    new_tier = compute_tier(pts)
    if account.tier != new_tier:
        account.tier = new_tier
        account.save(update_fields=["tier", "updated_at"])
    return pts


def award_points_for_order(order) -> int | None:
    """
    Awards loyalty points for a settled order. Call inside transaction.atomic().
    Returns points_earned (int) or None if order has no customer.
    """
    from apps.customers.models import LoyaltyAccount, LoyaltyTransaction

    if not order.customer_id:
        return None

    points_earned = math.floor(float(order.grand_total) / 10_000)
    if points_earned <= 0:
        return 0

    account, _ = LoyaltyAccount.objects.select_for_update().get_or_create(
        customer_id=order.customer_id
    )

    new_balance = account.points_balance + points_earned
    account.points_balance = new_balance
    account.save(update_fields=["points_balance", "updated_at"])

    LoyaltyTransaction.objects.create(
        account=account,
        txn_type=LoyaltyTransaction.TxnType.EARN,
        points=points_earned,
        balance_after=new_balance,
        reference_type="order",
        reference_id=order.id,
        note=f"Points earned from order {order.order_number}",
    )

    recompute_and_save_tier(account)

    return points_earned
