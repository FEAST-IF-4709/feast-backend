"""Tests for apps.orders.utils.generate_order_number."""
import datetime
import re
import threading

import pytest

from apps.orders.utils import generate_order_number


ORDER_NUMBER_RE = re.compile(r"^FT-\d{8}-\d{6}$")


class TestGenerateOrderNumberFormat:
    def test_matches_expected_format(self, db):
        number = generate_order_number()
        assert ORDER_NUMBER_RE.match(number), f"Unexpected format: {number!r}"

    def test_prefix_is_ft(self, db):
        assert generate_order_number().startswith("FT-")

    def test_date_segment_matches_given_date(self, db):
        target = datetime.date(2026, 1, 15)
        number = generate_order_number(date=target)
        assert "20260115" in number


class TestGenerateOrderNumberSequencing:
    def test_sequential_calls_increment(self, db):
        d = datetime.date(2030, 6, 1)
        first = generate_order_number(date=d)
        second = generate_order_number(date=d)
        seq_first = int(first.split("-")[2])
        seq_second = int(second.split("-")[2])
        assert seq_second == seq_first + 1

    def test_different_days_reset_to_one(self, db):
        day1 = datetime.date(2030, 7, 1)
        day2 = datetime.date(2030, 7, 2)
        n1 = generate_order_number(date=day1)
        n2 = generate_order_number(date=day2)
        assert int(n1.split("-")[2]) == 1
        assert int(n2.split("-")[2]) == 1

    def test_same_day_never_repeats(self, db):
        d = datetime.date(2030, 8, 1)
        numbers = [generate_order_number(date=d) for _ in range(20)]
        assert len(set(numbers)) == 20


class TestGenerateOrderNumberConcurrency:
    def test_10_threads_produce_unique_numbers(self, db):
        """Simulate concurrent order creation from 10 threads.

        Each thread calls generate_order_number for the same calendar day; the
        resulting set must have exactly 10 unique values — no duplicates.
        """
        d = datetime.date(2030, 9, 1)
        results: list[str] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker():
            try:
                number = generate_order_number(date=d)
                with lock:
                    results.append(number)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors in threads: {errors}"
        assert len(results) == 10
        assert len(set(results)) == 10, f"Duplicates found: {results}"
