from datetime import datetime, timezone

from atd_radius.infrastructure.login_reservations import PostgresLoginReservationRepository


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
        if sql.lstrip().startswith("SELECT request_key, ras_id, username, created_at"):
            return Result(self.rows)
        return Result()


def test_request_key_is_stable_for_retransmission_and_bound_to_peer_and_authenticator():
    class Packet:
        identifier = 9
        authenticator = bytes(range(16))
    packet = Packet()
    key = PostgresLoginReservationRepository.request_key(packet, ("192.0.2.1", 1812))
    assert key == PostgresLoginReservationRepository.request_key(packet, ("192.0.2.1", 1812))
    assert key != PostgresLoginReservationRepository.request_key(packet, ("192.0.2.2", 1812))
    assert len(key) == 64


def test_user_admission_lock_reservation_and_start_handoff_are_database_scoped():
    conn = Connection()
    repo = PostgresLoginReservationRepository(conn)
    repo.lock_user(7)
    assert "pg_advisory_xact_lock" in conn.calls[-1][0]
    assert conn.calls[-1][1] == ("login:7",)
    repo.reserve(7, 3, "a" * 64, "alice", False)
    sql, params = conn.calls[-1]
    assert "INSERT INTO atd_radius_login_reservations" in sql
    assert "ON CONFLICT (request_key) DO NOTHING" in sql
    assert params == (7, 3, "a" * 64, "alice", False)
    repo.consume_one(7, 3)
    assert "DELETE FROM atd_radius_login_reservations" in conn.calls[-1][0]
    assert conn.calls[-1][1] == (7, 3)


def test_reservation_provider_excludes_only_the_current_retransmitted_request():
    from atd_radius.application.radius_runtime import session_views
    from atd_radius.domain.radius_runtime import SessionRegistry
    from atd_radius.infrastructure.login_reservations import LoginReservation

    created = datetime(2026, 10, 20, tzinfo=timezone.utc)
    class Reservations:
        def list_active(self, user_id, exclude_request_key=None):
            assert user_id == 7
            return tuple(
                item for item in (
                    LoginReservation("prior", 3, "alice", created, False),
                    LoginReservation("current", 3, "alice", created, True),
                ) if item.request_key != exclude_request_key
            )

    views = session_views(SessionRegistry(), Reservations(), "current")(7)
    assert len(views) == 1
    assert views[0].unique_id == "login:prior"
    assert views[0].ras_multi_login_allowed is False
