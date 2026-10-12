from datetime import datetime
from decimal import Decimal

import pytest

from atd_radius.infrastructure.ias_events_repository import (
    EVENT_TYPES,
    PostgresIASEventRepository,
)


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)
    def fetchall(self):
        return self.rows
    def fetchone(self):
        return self.rows[0] if self.rows else None


class Conn:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self.responses.pop(0) if self.responses else Result()


def test_list_ias_events_maps_native_fields_and_pagination():
    conn = Conn([Result([(
        17, 1, datetime(2026, 10, 12, 10), "admin",
        Decimal("25.00"), "1,2", "credit correction",
    )])])
    events = PostgresIASEventRepository(conn).list_events(10, 20, 21)
    assert len(events) == 1
    assert events[0].event_type_name == "CHANGE_CREDIT"
    assert events[0].destinations == "1,2"
    assert conn.calls[0][1] == (10, 20, 1)
    assert "event_id > %s" in conn.calls[0][0]
    assert "ORDER BY event_id" in conn.calls[0][0]


def test_ias_event_range_rejects_unbounded_or_oversized_ranges():
    repo = PostgresIASEventRepository(Conn([]))
    with pytest.raises(ValueError):
        repo.list_events(0, 20, 20)
    with pytest.raises(ValueError):
        repo.list_events(0, 0, 3001)


def test_delete_ias_events_uses_parameterized_ids_and_counts_matches():
    conn = Conn([Result([(3,)]), Result([]), Result([(9,)])])
    deleted = PostgresIASEventRepository(conn).delete_events([3, 4, 9])
    assert deleted == 2
    assert all("DELETE FROM ias_event WHERE event_id = %s" in sql for sql, _ in conn.calls)
    assert [params for _, params in conn.calls] == [(3,), (4,), (9,)]


def test_ias_event_type_mapping_preserves_source_order():
    assert EVENT_TYPES == (
        "CHANGE_CREDIT", "CHANGE_DEPOSIT", "ADD_USER",
        "DELETE_USER", "ADD_ADMIN", "DELETE_ADMIN",
    )
