from __future__ import annotations

import datetime

from django.db import connection
from django.utils import timezone


def generate_order_number(date: datetime.date | None = None) -> str:
    """Generate a globally unique daily order number in the format FT-YYYYMMDD-XXXXXX.

    Uses a PostgreSQL ON CONFLICT upsert against `orders_dailyordercounter` for
    atomic, lock-free increment — no Redis dependency.  The counter is global
    (not scoped per brand/outlet) so the result satisfies the model's
    `order_number unique=True` constraint across all tenants.
    """
    if date is None:
        date = timezone.now().date()
    date_str = date.strftime("%Y%m%d")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO orders_dailyordercounter (date, last_sequence)
            VALUES (%s, 1)
            ON CONFLICT (date) DO UPDATE
              SET last_sequence = orders_dailyordercounter.last_sequence + 1
            RETURNING last_sequence
            """,
            [date],
        )
        seq = cursor.fetchone()[0]
    return f"FT-{date_str}-{seq:06d}"
