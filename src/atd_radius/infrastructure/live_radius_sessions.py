"""Durable active RADIUS session state for restart recovery.

This is an ATD operational extension; it does not replace native IBSng
connection_log/history tables. The JSON snapshot preserves charging baselines
that cannot be reconstructed from connection_log alone.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from atd_radius.domain.radius_runtime import SessionKey, SessionState
from atd_radius.domain.voip_tariff import VoipPrefix


class SessionStateConnection(Protocol):
    def execute(self, sql: str, params=()): ...


def _date(value):
    if value in (None, ""):
        return None
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


class PostgresLiveRadiusSessionRepository:
    """Persist active state inside the same transaction as native accounting."""

    def __init__(self, conn: SessionStateConnection) -> None:
        self.conn = conn

    @staticmethod
    def _encode(state: SessionState) -> str:
        prefix = state.voip_current_prefix
        prefix_data = None
        if prefix is not None:
            prefix_data = {
                "prefix_id": prefix.prefix_id, "code": prefix.code, "name": prefix.name,
                "cpm": str(prefix.cpm), "free_seconds": prefix.free_seconds,
                "min_duration": prefix.min_duration, "round_to": prefix.round_to,
                "min_chargeable_duration": prefix.min_chargeable_duration,
            }
        payload = {
            "attributes": {str(k): str(v) for k, v in state.attributes.items()},
            "started": state.started, "stopped": state.stopped,
            "input_octets": state.input_octets, "output_octets": state.output_octets,
            "started_at": state.started_at.isoformat() if state.started_at else None,
            "charge_id": state.charge_id, "charge_kind": state.charge_kind,
            "charge_rule_id": state.charge_rule_id,
            "charge_rule_started_at": state.charge_rule_started_at.isoformat() if state.charge_rule_started_at else None,
            "charge_rule_input_octets": state.charge_rule_input_octets,
            "charge_rule_output_octets": state.charge_rule_output_octets,
            "charge_accrued": str(state.charge_accrued),
            "voip_call_started_at": state.voip_call_started_at.isoformat() if state.voip_call_started_at else None,
            "voip_free_seconds_remaining": state.voip_free_seconds_remaining,
            "voip_current_prefix": prefix_data, "voip_missed_call": state.voip_missed_call,
            "ras_multi_login_allowed": state.ras_multi_login_allowed,
            "termination_requested_reason": state.termination_requested_reason,
            "termination_requested_at": state.termination_requested_at.isoformat() if state.termination_requested_at else None,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _decode(user_id: int, ras_id: int, unique_id: str, payload) -> SessionState:
        if isinstance(payload, str):
            payload = json.loads(payload)
        prefix_data = payload.get("voip_current_prefix")
        prefix = None
        if prefix_data is not None:
            prefix = VoipPrefix(
                prefix_id=int(prefix_data["prefix_id"]), code=str(prefix_data["code"]),
                name=str(prefix_data["name"]), cpm=Decimal(str(prefix_data["cpm"])),
                free_seconds=int(prefix_data["free_seconds"]), min_duration=int(prefix_data["min_duration"]),
                round_to=int(prefix_data["round_to"]),
                min_chargeable_duration=int(prefix_data["min_chargeable_duration"]),
            )
        return SessionState(
            key=SessionKey(int(user_id), int(ras_id), str(unique_id)),
            attributes={str(k): str(v) for k, v in payload.get("attributes", {}).items()},
            started=bool(payload.get("started", True)), stopped=bool(payload.get("stopped", False)),
            input_octets=max(0, int(payload.get("input_octets", 0))),
            output_octets=max(0, int(payload.get("output_octets", 0))),
            started_at=_date(payload.get("started_at")),
            charge_id=int(payload["charge_id"]) if payload.get("charge_id") is not None else None,
            charge_kind=str(payload["charge_kind"]) if payload.get("charge_kind") is not None else None,
            charge_rule_id=int(payload["charge_rule_id"]) if payload.get("charge_rule_id") is not None else None,
            charge_rule_started_at=_date(payload.get("charge_rule_started_at")),
            charge_rule_input_octets=max(0, int(payload.get("charge_rule_input_octets", 0))),
            charge_rule_output_octets=max(0, int(payload.get("charge_rule_output_octets", 0))),
            charge_accrued=Decimal(str(payload.get("charge_accrued", "0"))),
            voip_call_started_at=_date(payload.get("voip_call_started_at")),
            voip_free_seconds_remaining=int(payload.get("voip_free_seconds_remaining", 0)),
            voip_current_prefix=prefix, voip_missed_call=bool(payload.get("voip_missed_call", False)),
            ras_multi_login_allowed=payload.get("ras_multi_login_allowed"),
            termination_requested_reason=payload.get("termination_requested_reason"),
            termination_requested_at=_date(payload.get("termination_requested_at")),
        )

    def save(self, state: SessionState) -> None:
        if not state.started or state.stopped:
            self.delete(state.key)
            return
        self.conn.execute(
            """
            INSERT INTO atd_radius_live_sessions (user_id, ras_id, unique_id, state)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (user_id, ras_id, unique_id)
            DO UPDATE SET state=EXCLUDED.state, updated_at=CURRENT_TIMESTAMP
            """,
            (state.key.user_id, state.key.ras_id, state.key.unique_id, self._encode(state)),
        )

    def delete(self, key: SessionKey) -> None:
        self.conn.execute(
            "DELETE FROM atd_radius_live_sessions WHERE user_id=%s AND ras_id=%s AND unique_id=%s",
            (key.user_id, key.ras_id, key.unique_id),
        )

    def list_active(self) -> list[SessionState]:
        rows = self.conn.execute(
            "SELECT user_id, ras_id, unique_id, state FROM atd_radius_live_sessions ORDER BY user_id, ras_id, unique_id"
        ).fetchall()
        states = []
        for row in rows:
            state = self._decode(int(row[0]), int(row[1]), str(row[2]), row[3])
            if state.started and not state.stopped:
                states.append(state)
            else:
                self.delete(state.key)
        return states
