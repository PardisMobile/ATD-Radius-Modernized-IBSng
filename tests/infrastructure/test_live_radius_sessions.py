from datetime import datetime, timezone
from decimal import Decimal

from atd_radius.domain.radius_runtime import SessionKey, SessionState
from atd_radius.domain.voip_tariff import VoipPrefix
from atd_radius.infrastructure.live_radius_sessions import PostgresLiveRadiusSessionRepository


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)
    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if sql.startswith("SELECT user_id, ras_id, unique_id, state"):
            return Result(self.rows)
        return Result()


def test_live_session_snapshot_round_trips_all_charge_and_voip_state():
    conn = Connection()
    repo = PostgresLiveRadiusSessionRepository(conn)
    started = datetime(2026, 10, 20, 12, 30, tzinfo=timezone.utc)
    state = SessionState(
        key=SessionKey(7, 3, "call-7"),
        attributes={"User-Name": "sip-alice", "__connection_log_id": "100"},
        started=True, input_octets=1200, output_octets=3400, started_at=started,
        charge_id=9, charge_kind="voip", charge_rule_id=11, charge_rule_started_at=started,
        charge_rule_input_octets=100, charge_rule_output_octets=200,
        charge_accrued=Decimal("12.375"), voip_call_started_at=started,
        voip_free_seconds_remaining=17,
        voip_current_prefix=VoipPrefix(22, "98", "Iran", Decimal("60.5"), 30, 10, 60, 15),
        ras_multi_login_allowed=True, termination_requested_reason="credit_finished",
        termination_requested_at=started,
    )
    restored = repo._decode(7, 3, "call-7", repo._encode(state))
    assert restored.key == state.key
    assert dict(restored.attributes) == dict(state.attributes)
    assert (restored.input_octets, restored.output_octets) == (1200, 3400)
    assert (restored.charge_id, restored.charge_kind, restored.charge_rule_id) == (9, "voip", 11)
    assert restored.charge_rule_started_at == started
    assert restored.charge_accrued == Decimal("12.375")
    assert restored.voip_free_seconds_remaining == 17
    assert restored.voip_current_prefix == state.voip_current_prefix
    assert restored.ras_multi_login_allowed is True
    assert restored.termination_requested_reason == "credit_finished"


def test_live_session_repository_upserts_and_deletes_by_full_native_session_key():
    conn = Connection()
    repo = PostgresLiveRadiusSessionRepository(conn)
    state = SessionState(
        key=SessionKey(7, 3, "sid"), attributes={"Acct-Session-Id": "sid"},
        started=True, started_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
    )
    repo.save(state)
    sql, params = conn.calls[-1]
    assert "INSERT INTO atd_radius_live_sessions" in sql
    assert "ON CONFLICT (user_id, ras_id, unique_id)" in sql
    assert params[:3] == (7, 3, "sid")
    repo.delete(state.key)
    assert conn.calls[-1] == (
        "DELETE FROM atd_radius_live_sessions WHERE user_id=%s AND ras_id=%s AND unique_id=%s",
        (7, 3, "sid"),
    )


def test_stopped_or_unstarted_state_is_not_persisted_as_active():
    conn = Connection()
    repo = PostgresLiveRadiusSessionRepository(conn)
    state = SessionState(key=SessionKey(7, 3, "sid"), started=True, stopped=True)
    repo.save(state)
    assert conn.calls[0][0].startswith("DELETE FROM atd_radius_live_sessions")


def test_list_active_decodes_postgres_jsonb_snapshot():
    started = datetime(2026, 10, 20, 13, 0, tzinfo=timezone.utc)
    original = SessionState(
        key=SessionKey(9, 4, "restored"),
        attributes={"Acct-Session-Id": "restored", "no_connection_log": "1"},
        started=True, input_octets=123, output_octets=456, started_at=started,
        charge_id=18, charge_kind="internet", charge_accrued=Decimal("2.75"),
    )
    payload = PostgresLiveRadiusSessionRepository._encode(original)
    conn = Connection([(9, 4, "restored", payload)])
    restored = PostgresLiveRadiusSessionRepository(conn).list_active()
    assert len(restored) == 1
    assert restored[0].key == original.key
    assert restored[0].charge_accrued == Decimal("2.75")
    assert restored[0].attributes["no_connection_log"] == "1"
