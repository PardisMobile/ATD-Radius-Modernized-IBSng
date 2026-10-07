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


pytestmark = pytest.mark.integration


@pytest.fixture()
def live_db():
    dsn = os.getenv("ATD_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("ATD_TEST_DATABASE_URL is not configured")
    with psycopg.connect(dsn) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        for name in ("migrations/001_initial.sql", "migrations/002_functions.sql"):
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
        thread = threading.Thread(target=_serve_one, args=(server,), daemon=True)
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
        thread = threading.Thread(target=_serve_one, args=(server,), daemon=True)
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
        thread = threading.Thread(target=_serve_one, args=(server,), daemon=True)
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
