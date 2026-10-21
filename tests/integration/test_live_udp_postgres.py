from __future__ import annotations

import hashlib
import os
import socket
import threading
from pathlib import Path

import psycopg
import pytest

from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import decode, encode
from atd_radius.infrastructure.radius_udp import RadiusUDPServer
from atd_radius.infrastructure.voip_charge_rules import (
    PostgresVoipChargeRuleRepository,
    VoipChargeRuleInput,
)
from atd_radius.infrastructure.charges import ChargeInUseError, PostgresChargeRepository



@pytest.fixture()
def live_db():
    dsn = os.getenv("ATD_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("ATD_TEST_DATABASE_URL is not configured")
    with psycopg.connect(dsn) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        for name in ("migrations/001_initial.sql", "migrations/002_functions.sql", "migrations/007_live_radius_sessions.sql", "migrations/008_login_reservations.sql"):
            conn.execute(Path(name).read_text(encoding="utf-8"))
        conn.execute(
            """
            INSERT INTO ras (ras_id, ras_description, ras_ip, ras_type, radius_secret, active)
            VALUES (1, 'live-mikrotik', '127.0.0.1', 'MikroTik', 'shared', true)
            """
        )
        conn.execute(
            """
            INSERT INTO users (user_id, credit, owner_id, group_id)
            VALUES (1, 100, NULL, NULL)
            """
        )
        conn.execute(
            """
            INSERT INTO normal_users (user_id, normal_username, normal_password)
            VALUES (1, 'live-user', 'password')
            """
        )
        conn.commit()
        yield dsn


def _accounting_request(identifier: int, attrs: dict[str, object], secret: str) -> bytes:
    request = RadiusPacket(
        RadiusCode.ACCOUNTING_REQUEST,
        identifier,
        attrs,
        bytes(16),
    )
    wire = bytearray(encode(request, secret))
    digest = hashlib.md5(wire[:4] + bytes(16) + wire[20:] + secret.encode()).digest()
    wire[4:20] = digest
    return bytes(wire)


def _serve_one(server: RadiusUDPServer, errors: list[BaseException]) -> None:
    try:
        server.serve_once()
    except BaseException as exc:
        errors.append(exc)


def test_live_udp_accounting_round_trip_persists_connection_log(live_db):
    state = NativeRadiusRuntimeState()
    handler = NativeRadiusPacketHandler(state, lambda: psycopg.connect(live_db))
    server = RadiusUDPServer(handler, type("Secrets", (), {"secret_for_ip": lambda self, ip: "shared"})(), host="127.0.0.1", port=0)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    server._socket = sock
    destination = sock.getsockname()

    try:
        start = _accounting_request(
            7,
            {
                "User-Name": "live-user",
                "Acct-Status-Type": 1,
                "Acct-Session-Id": "wire-session",
                "NAS-Port": 17,
                "Framed-IP-Address": "10.10.10.10",
                "Acct-Input-Octets": 0,
                "Acct-Output-Octets": 0,
            },
            "shared",
        )
        errors: list[BaseException] = []
        thread = threading.Thread(target=_serve_one, args=(server, errors), daemon=True)
        thread.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(3)
            client.sendto(start, destination)
            response, _ = client.recvfrom(4096)
        thread.join(timeout=3)
        assert not errors
        assert decode(response, "shared").code is RadiusCode.ACCOUNTING_RESPONSE

        with psycopg.connect(live_db) as verify:
            row = verify.execute(
                "SELECT user_id, ras_id, login_time, logout_time FROM connection_log WHERE user_id=1 ORDER BY connection_log_id DESC LIMIT 1"
            ).fetchone()
            assert row is not None
            assert row[0] == 1
            assert row[1] == 1
            assert row[2] is not None
            assert row[3] is None

        stop = _accounting_request(
            8,
            {
                "User-Name": "live-user",
                "Acct-Status-Type": 2,
                "Acct-Session-Id": "wire-session",
                "NAS-Port": 17,
                "Framed-IP-Address": "10.10.10.10",
                "Acct-Input-Octets": 100,
                "Acct-Output-Octets": 200,
            },
            "shared",
        )
        thread = threading.Thread(target=_serve_one, args=(server, errors), daemon=True)
        thread.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(3)
            client.sendto(stop, destination)
            response, _ = client.recvfrom(4096)
        thread.join(timeout=3)
        assert decode(response, "shared").code is RadiusCode.ACCOUNTING_RESPONSE

        with psycopg.connect(live_db) as verify:
            row = verify.execute(
                "SELECT login_time, logout_time FROM connection_log WHERE user_id=1 ORDER BY connection_log_id DESC LIMIT 1"
            ).fetchone()
            assert row is not None
            assert row[0] is not None
            assert row[1] is not None
            detail = verify.execute(
                """
                SELECT value FROM connection_log_details
                WHERE connection_log_id=(SELECT max(connection_log_id) FROM connection_log)
                  AND name='Acct-Session-Id'
                """
            ).fetchone()
            assert detail == ("wire-session",)
    finally:
        server.close()


def test_live_transaction_rolls_back_connection_log_and_credit_on_settlement_failure(live_db):
    with psycopg.connect(live_db) as conn:
        conn.execute("UPDATE users SET credit=100 WHERE user_id=1")
        conn.execute("INSERT INTO charges (charge_id, name, charge_type) VALUES (1, 'live-charge', 'internet')")
        conn.execute(
            """
            INSERT INTO internet_charge_rules
              (charge_rule_id, charge_id, start_time, end_time, ras_id, cpm, cpk, assumed_kps, bandwidth_limit_kbytes)
            VALUES (1, 1, '00:00:00', '23:59:59', 1, 0, 1, 0, -1)
            """
        )
        conn.execute(
            "INSERT INTO charge_rule_day_of_weeks (charge_rule_id, day_of_week) VALUES (1, 0),(1,1),(1,2),(1,3),(1,4),(1,5),(1,6)"
        )
        # A1.24 treats only the explicit _ALL_ marker as a wildcard port.
        conn.execute(
            "INSERT INTO charge_rule_ports (charge_rule_id, ras_port) VALUES (1, '_ALL_')"
        )
        conn.execute(
            """
            INSERT INTO user_attrs (user_id, attr_name, attr_value)
            VALUES (1, 'normal_charge', '1')
            ON CONFLICT (user_id, attr_name) DO UPDATE SET attr_value=EXCLUDED.attr_value
            """
        )
        conn.execute(
            """
            CREATE OR REPLACE FUNCTION atd_fail_credit_update() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'forced settlement failure';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        conn.execute(
            """
            CREATE TRIGGER atd_fail_credit_update_trigger
            AFTER UPDATE OF credit ON users
            FOR EACH ROW EXECUTE FUNCTION atd_fail_credit_update()
            """
        )
        conn.commit()

    state = NativeRadiusRuntimeState()
    handler = NativeRadiusPacketHandler(state, lambda: psycopg.connect(live_db))
    server = RadiusUDPServer(handler, type("Secrets", (), {"secret_for_ip": lambda self, ip: "shared"})(), host="127.0.0.1", port=0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    server._socket = sock
    destination = sock.getsockname()

    try:
        errors: list[BaseException] = []
        start = _accounting_request(
            20,
            {
                "User-Name": "live-user",
                "Acct-Status-Type": 1,
                "Acct-Session-Id": "rollback-session",
                "NAS-Port": 17,
                "Framed-IP-Address": "10.10.10.11",
                "Acct-Input-Octets": 0,
                "Acct-Output-Octets": 0,
            },
            "shared",
        )
        thread = threading.Thread(target=_serve_one, args=(server, errors), daemon=True)
        thread.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(3)
            client.sendto(start, destination)
            client.recvfrom(4096)
        thread.join(timeout=3)

        stop = _accounting_request(
            21,
            {
                "User-Name": "live-user",
                "Acct-Status-Type": 2,
                "Acct-Session-Id": "rollback-session",
                "NAS-Port": 17,
                "Framed-IP-Address": "10.10.10.11",
                "Acct-Input-Octets": 1024,
                "Acct-Output-Octets": 0,
            },
            "shared",
        )
        thread = threading.Thread(target=_serve_one, args=(server, errors), daemon=True)
        thread.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(3)
            client.sendto(stop, destination)
            with pytest.raises(socket.timeout):
                client.recvfrom(4096)
        thread.join(timeout=3)
        assert errors and "forced settlement failure" in str(errors[0])

        with psycopg.connect(live_db) as verify:
            assert verify.execute("SELECT credit FROM users WHERE user_id=1").fetchone() == (100,)
            assert verify.execute(
                "SELECT count(*) FROM connection_log WHERE connection_log_id=(SELECT max(connection_log_id) FROM connection_log) AND logout_time IS NULL"
            ).fetchone() == (1,)
    finally:
        with psycopg.connect(live_db) as cleanup:
            cleanup.execute("DROP TRIGGER IF EXISTS atd_fail_credit_update_trigger ON users")
            cleanup.execute("DROP FUNCTION IF EXISTS atd_fail_credit_update()")
            cleanup.commit()
        server.close()


def test_postgres_voip_charge_rule_create_update_delete_round_trip(live_db):
    with psycopg.connect(live_db) as conn:
        conn.execute(
            "INSERT INTO charges (charge_id, name, charge_type) VALUES (1, 'live-voip', 'VoIP')"
        )
        conn.execute(
            "INSERT INTO voip_charge_rule_tariff (tariff_id, tariff_name, comment) VALUES (1, 'Business', '')"
        )
        conn.execute(
            "INSERT INTO ras_ports (ras_id, port_name, type) VALUES (1, 'ppp0', 'PPP')"
        )
        conn.commit()

    payload = VoipChargeRuleInput(
        start_time="08:00",
        end_time="18:00",
        days=("Monday", "Tuesday"),
        tariff_name="Business",
        ras_id=1,
        ports=("ppp0",),
    )
    with psycopg.connect(live_db) as conn:
        repo = PostgresVoipChargeRuleRepository(conn)
        rule_id = repo.create("live-voip", payload)
        conn.commit()

    with psycopg.connect(live_db) as conn:
        rule = PostgresVoipChargeRuleRepository(conn).get(rule_id)
        assert rule is not None
        assert rule.charge_id == 1
        assert rule.tariff_id == 1
        assert rule.days == frozenset({0, 1})
        assert rule.ports == frozenset({"ppp0"})
        assert rule.ras_id == 1

    updated = VoipChargeRuleInput(
        start_time="09:00",
        end_time="17:00",
        days=("Wednesday",),
        tariff_name="Business",
        ras_id=1,
        ports=("ppp0",),
    )
    with psycopg.connect(live_db) as conn:
        PostgresVoipChargeRuleRepository(conn).update("live-voip", rule_id, updated)
        conn.commit()

    with psycopg.connect(live_db) as conn:
        rule = PostgresVoipChargeRuleRepository(conn).get(rule_id)
        assert rule is not None
        assert rule.start_second == 9 * 3600
        assert rule.end_second == 17 * 3600
        assert rule.days == frozenset({2})

    with psycopg.connect(live_db) as conn:
        PostgresVoipChargeRuleRepository(conn).delete("live-voip", rule_id)
        conn.commit()

    with psycopg.connect(live_db) as conn:
        repo = PostgresVoipChargeRuleRepository(conn)
        assert repo.get(rule_id) is None
        assert conn.execute(
            "SELECT count(*) FROM charge_rule_ports WHERE charge_rule_id = %s",
            (rule_id,),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT count(*) FROM charge_rule_day_of_weeks WHERE charge_rule_id = %s",
            (rule_id,),
        ).fetchone()[0] == 0


def test_postgres_internet_charge_rule_create_update_delete_round_trip(live_db):
    from decimal import Decimal
    from atd_radius.infrastructure.billing_rules import (
        InternetChargeRuleInput,
        PostgresInternetChargeRuleRepository,
    )

    with psycopg.connect(live_db) as conn:
        conn.execute(
            "INSERT INTO charges (charge_id, name, charge_type) VALUES (1, 'live-internet', 'Internet')"
        )
        conn.execute(
            "INSERT INTO ras_ports (ras_id, port_name, type) VALUES (1, 'ppp0', 'PPP')"
        )
        conn.commit()

    payload = InternetChargeRuleInput(
        start_time="08:00", end_time="18:00", days=("Monday", "Tuesday"),
        cpm=Decimal("2.50"), cpk=Decimal("0.25"), assumed_kps=128,
        bandwidth_limit_kbytes=4096, tx_leaf_name="", rx_leaf_name="",
        ras_id=1, ports=("ppp0",),
    )
    with psycopg.connect(live_db) as conn:
        repo = PostgresInternetChargeRuleRepository(conn)
        rule_id = repo.create("live-internet", payload)
        conn.commit()

    with psycopg.connect(live_db) as conn:
        rule = PostgresInternetChargeRuleRepository(conn).get(rule_id)
        assert rule is not None
        assert rule.charge_id == 1
        assert rule.cpm == Decimal("2.50")
        assert rule.bw_transmit_leaf_id is None
        assert rule.days == frozenset({0, 1})

    updated = InternetChargeRuleInput(
        start_time="09:00", end_time="17:00", days=("Wednesday",),
        cpm=Decimal("3.00"), cpk=Decimal("0.50"), assumed_kps=256,
        bandwidth_limit_kbytes=8192, tx_leaf_name="", rx_leaf_name="",
        ras_id=1, ports=("ppp0",),
    )
    with psycopg.connect(live_db) as conn:
        PostgresInternetChargeRuleRepository(conn).update("live-internet", rule_id, updated)
        conn.commit()

    with psycopg.connect(live_db) as conn:
        rule = PostgresInternetChargeRuleRepository(conn).get(rule_id)
        assert rule is not None
        assert rule.start_second == 9 * 3600
        assert rule.cpm == Decimal("3.00")
        assert rule.assumed_kps == 256
        assert rule.days == frozenset({2})

    with psycopg.connect(live_db) as conn:
        PostgresInternetChargeRuleRepository(conn).delete("live-internet", rule_id)
        conn.commit()

    with psycopg.connect(live_db) as conn:
        assert PostgresInternetChargeRuleRepository(conn).get(rule_id) is None


def test_postgres_charge_catalog_update_and_source_delete_guard(live_db):
    with psycopg.connect(live_db) as conn:
        conn.execute(
            "INSERT INTO admins (admin_id, username, password, name) VALUES (7, 'admin', repeat('a', 34), 'Admin')"
        )
        conn.commit()

    with psycopg.connect(live_db) as conn:
        repo = PostgresChargeRepository(conn)
        charge_id = repo.create("live-internet", "initial", "Internet", 7, False)
        conn.commit()

    with psycopg.connect(live_db) as conn:
        repo = PostgresChargeRepository(conn)
        charge = repo.get(charge_id)
        assert charge is not None
        assert charge.name == "live-internet"
        assert charge.charge_type == "Internet"
        assert charge.admin_id == 7
        repo.update(charge_id, "renamed-internet", "updated", True)
        conn.commit()

    with psycopg.connect(live_db) as conn:
        conn.execute(
            "INSERT INTO internet_charge_rules (charge_id, charge_rule_id, start_time, end_time, cpm, cpk, assumed_kps, bandwidth_limit_kbytes) VALUES (%s, 99, '08:00:00', '18:00:00', 1, 1, 128, 4096)",
            (charge_id,),
        )
        conn.execute(
            "INSERT INTO charge_rule_ports (charge_rule_id, ras_port) VALUES (99, '_ALL_')"
        )
        conn.execute(
            "INSERT INTO charge_rule_day_of_weeks (charge_rule_id, day_of_week) VALUES (99, 0)"
        )
        conn.execute(
            "INSERT INTO user_attrs (user_id, attr_name, attr_value) VALUES (1, 'normal_charge', %s)",
            (str(charge_id),),
        )
        conn.commit()

    with psycopg.connect(live_db) as conn:
        import pytest
        with pytest.raises(ChargeInUseError):
            PostgresChargeRepository(conn).delete("renamed-internet")

    with psycopg.connect(live_db) as conn:
        conn.execute("DELETE FROM user_attrs WHERE user_id=1 AND attr_name='normal_charge'")
        PostgresChargeRepository(conn).delete("renamed-internet")
        conn.commit()

    with psycopg.connect(live_db) as conn:
        assert conn.execute("SELECT count(*) FROM charges WHERE charge_id=%s", (charge_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM internet_charge_rules WHERE charge_rule_id=99").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM charge_rule_ports WHERE charge_rule_id=99").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM charge_rule_day_of_weeks WHERE charge_rule_id=99").fetchone()[0] == 0


def test_postgres_user_charge_assignment_round_trip_for_normal_and_voip(live_db):
    from atd_radius.infrastructure.user_charge_assignments import UserChargeAssignmentRepository

    with psycopg.connect(live_db) as conn:
        conn.execute(
            "INSERT INTO admins (admin_id, username, password, name) VALUES (7, 'admin', repeat('a', 34), 'Admin')"
        )
        conn.execute(
            "INSERT INTO charges (charge_id, name, comment, charge_type, admin_id, visible_to_all) VALUES (11, 'InternetPlan', '', 'Internet', 7, true), (12, 'VoIPPlan', '', 'VoIP', 7, true)"
        )
        conn.execute(
            "INSERT INTO voip_users (user_id, voip_username, voip_password) VALUES (1, 'live-voip', 'password')"
        )
        conn.commit()

    for username, attribute_name, charge_name, expected_id in [
        ("live-user", "normal_charge", "InternetPlan", 11),
        ("live-voip", "voip_charge", "VoIPPlan", 12),
    ]:
        with psycopg.connect(live_db) as conn:
            repo = UserChargeAssignmentRepository(conn)
            target = repo.lock_target(username, attribute_name)
            assert target is not None
            assigned = repo.assign(target, admin_id=7, charge_name=charge_name)
            conn.commit()
            assert assigned.charge_id == expected_id
            assert assigned.charge_name == charge_name

        with psycopg.connect(live_db) as conn:
            repo = UserChargeAssignmentRepository(conn)
            target = repo.lock_target(username, attribute_name)
            assert target is not None
            stored = repo.get(target)
            assert stored.charge_id == expected_id
            assert stored.charge_name == charge_name
            repo.delete(target, admin_id=7)
            conn.commit()

        with psycopg.connect(live_db) as conn:
            assert conn.execute(
                "SELECT count(*) FROM user_attrs WHERE user_id=1 AND attr_name=%s",
                (attribute_name,),
            ).fetchone()[0] == 0


def test_postgres_ias_event_list_and_delete_round_trip(live_db):
    from decimal import Decimal
    from atd_radius.infrastructure.ias_events_repository import PostgresIASEventRepository

    with psycopg.connect(live_db) as conn:
        conn.execute(
            "INSERT INTO ias_event (event_id, event_type, actor, amount, destinations, comment) VALUES (501, 1, 'admin', 25, '1,2', 'test event')"
        )
        conn.commit()

    with psycopg.connect(live_db) as conn:
        repo = PostgresIASEventRepository(conn)
        events = repo.list_events(0, 0, 10)
        event = next(item for item in events if item.event_id == 501)
        assert event.event_type_name == "CHANGE_CREDIT"
        assert event.amount == Decimal("25")
        assert event.destinations == "1,2"
        assert repo.delete_events([501]) == 1
        conn.commit()

    with psycopg.connect(live_db) as conn:
        assert conn.execute("SELECT count(*) FROM ias_event WHERE event_id=501").fetchone()[0] == 0


def test_postgres_ias_user_info_projection_round_trip(live_db):
    from decimal import Decimal
    from atd_radius.infrastructure.ias_user_info import PostgresIASUserInfoRepository

    with psycopg.connect(live_db) as conn:
        conn.execute(
            "UPDATE users SET credit=12.50 WHERE user_id=1"
        )
        conn.commit()

    with psycopg.connect(live_db) as conn:
        users = PostgresIASUserInfoRepository(conn).get_many([1])
        assert len(users) == 1
        assert users[0].user_id == 1
        assert users[0].credit == Decimal("12.50")
        assert users[0].normal_username == "live-user"


def test_live_postgres_user_deletion_refunds_and_cleans_native_history(live_db):
    from decimal import Decimal
    from atd_radius.infrastructure.user_deletion import UserDeletionRepository

    with psycopg.connect(live_db) as conn:
        conn.execute(
            "INSERT INTO admins (admin_id, username, deposit) VALUES (8, 'delete-admin', 10)"
        )
        conn.execute(
            "INSERT INTO defs (name, value, type) VALUES (%s, %s, %s)",
            ("IAS_ENABLED", "I1\n.", "integer"),
        )
        log_id = conn.execute("SELECT nextval('connection_log_id')").fetchone()[0]
        conn.execute(
            """
            INSERT INTO connection_log
                (connection_log_id, user_id, credit_used, login_time, logout_time,
                 successful, service, ras_id)
            VALUES (%s, 1, NULL, CURRENT_TIMESTAMP - INTERVAL '1 hour',
                    CURRENT_TIMESTAMP, TRUE, 1, 1)
            """,
            (log_id,),
        )
        conn.execute(
            "INSERT INTO connection_log_details (connection_log_id, name, value) VALUES (%s, 'sample', 'value')",
            (log_id,),
        )
        conn.execute(
            """
            INSERT INTO user_audit_log
                (admin_id, is_user, object_id, attr_name, old_value, new_value)
            VALUES (8, TRUE, 1, 'sample', 'old', 'new')
            """
        )

    with psycopg.connect(live_db) as conn:
        result = UserDeletionRepository(conn).delete(
            [1],
            admin_id=8,
            admin_username="delete-admin",
            remote_addr="192.0.2.10",
            comment="integration cleanup",
            delete_connection_logs=True,
            delete_audit_logs=True,
        )
        assert result.refunded_credit == Decimal("100.00")

    with psycopg.connect(live_db) as conn:
        assert conn.execute("SELECT count(*) FROM users WHERE user_id=1").fetchone()[0] == 0
        assert conn.execute("SELECT deposit FROM admins WHERE admin_id=8").fetchone()[0] == Decimal("110.00")
        credit = conn.execute(
            "SELECT action, per_user_credit, admin_credit FROM credit_change WHERE admin_id=8"
        ).fetchone()
        assert credit == (3, Decimal("0.00"), Decimal("-100.00"))
        ias = conn.execute(
            "SELECT event_type, actor, amount, destinations FROM ias_event"
        ).fetchone()
        assert ias == (4, "delete-admin", Decimal("0.00"), "1")
        assert conn.execute("SELECT count(*) FROM connection_log WHERE user_id=1").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM user_audit_log WHERE object_id=1").fetchone()[0] == 0
