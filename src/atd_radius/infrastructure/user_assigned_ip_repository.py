"""PostgreSQL lease authority for A1.24 per-user assign_ip.

Call operations inside the packet's database transaction. Transaction-scoped
advisory locks serialize allocation across processes; the unique INET index
prevents an address being leased to different users concurrently.
"""
from __future__ import annotations
from collections.abc import Iterable
from typing import Protocol

class AssignedIPConnection(Protocol):
    def execute(self, sql: str, params=()): ...

class PostgresUserAssignedIPRepository:
    def __init__(self, conn: AssignedIPConnection) -> None:
        self.conn = conn

    def lock_user(self, user_id: int) -> None:
        self.conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"assign-ip:{int(user_id)}",))

    @staticmethod
    def _configured(addresses: str | Iterable[str] | None) -> tuple[str, ...]:
        values = addresses.split(",") if isinstance(addresses, str) else (addresses or ())
        result, seen = [], set()
        for value in values:
            address = str(value).strip()
            if address and address not in seen:
                result.append(address); seen.add(address)
        return tuple(result)

    def reserve(self, user_id: int, addresses: str | Iterable[str] | None, request_key: str) -> str | None:
        if not request_key: raise ValueError("request_key is required")
        user_id = int(user_id); self.lock_user(user_id)
        existing = self.conn.execute("SELECT user_id,host(ip_address) FROM atd_radius_user_assigned_ip_leases WHERE request_key=%s FOR UPDATE", (request_key,)).fetchone()
        configured = self._configured(addresses)
        if existing is not None:
            if int(existing[0]) != user_id: raise ValueError("request key belongs to another user")
            address = str(existing[1]); return address if address in configured else None
        if not configured: return None
        self.conn.execute("DELETE FROM atd_radius_user_assigned_ip_leases WHERE user_id=%s AND status='pending' AND NOT (host(ip_address)=ANY(%s))", (user_id, list(configured)))
        for address in configured:
            row = self.conn.execute("INSERT INTO atd_radius_user_assigned_ip_leases(user_id,ip_address,status,request_key) VALUES(%s,%s::inet,'pending',%s) ON CONFLICT(ip_address) DO NOTHING RETURNING host(ip_address)", (user_id,address,request_key)).fetchone()
            if row is not None: return str(row[0])
        return None

    def reserve_specific(self, user_id: int, addresses: str | Iterable[str] | None, request_key: str, address: str) -> str | None:
        address = str(ip_address(str(address).strip()))
        if not request_key: raise ValueError("request_key is required")
        if address not in self._configured(addresses): return None
        user_id = int(user_id); self.lock_user(user_id)
        existing = self.conn.execute("SELECT user_id,host(ip_address) FROM atd_radius_user_assigned_ip_leases WHERE request_key=%s FOR UPDATE", (request_key,)).fetchone()
        if existing is not None:
            if int(existing[0]) != user_id or str(existing[1]) != address: raise ValueError("request key is already reserved differently")
            return address
        row = self.conn.execute("INSERT INTO atd_radius_user_assigned_ip_leases(user_id,ip_address,status,request_key) VALUES(%s,%s::inet,'pending',%s) ON CONFLICT(ip_address) DO NOTHING RETURNING host(ip_address)", (user_id,address,request_key)).fetchone()
        return str(row[0]) if row is not None else None

    def bind_session(self, user_id: int, ras_id: int, session_id: str, address: str) -> bool:
        if not session_id or not address: return False
        user_id, ras_id = int(user_id), int(ras_id); self.lock_user(user_id)
        row = self.conn.execute("UPDATE atd_radius_user_assigned_ip_leases SET status='active',request_key=NULL,ras_id=%s,session_id=%s,updated_at=CURRENT_TIMESTAMP WHERE user_id=%s AND ip_address=%s::inet AND status='pending' RETURNING lease_id", (ras_id,str(session_id),user_id,str(address))).fetchone()
        if row is not None: return True
        existing = self.conn.execute("SELECT host(ip_address) FROM atd_radius_user_assigned_ip_leases WHERE user_id=%s AND ras_id=%s AND session_id=%s AND status='active' FOR UPDATE", (user_id,ras_id,str(session_id))).fetchone()
        if existing is not None:
            if str(existing[0]) != str(address): raise ValueError("session already owns a different address")
            return True
        return False

    def release_request(self, request_key: str) -> bool:
        row = self.conn.execute("DELETE FROM atd_radius_user_assigned_ip_leases WHERE request_key=%s AND status='pending' RETURNING lease_id", (request_key,)).fetchone()
        return row is not None

    def release_session(self, user_id: int, ras_id: int, session_id: str) -> str | None:
        user_id = int(user_id); self.lock_user(user_id)
        row = self.conn.execute("DELETE FROM atd_radius_user_assigned_ip_leases WHERE user_id=%s AND ras_id=%s AND session_id=%s AND status='active' RETURNING host(ip_address)", (user_id,int(ras_id),str(session_id))).fetchone()
        return str(row[0]) if row is not None else None

    def snapshot(self, user_id: int):
        rows = self.conn.execute("SELECT host(ip_address),status,ras_id::text,session_id FROM atd_radius_user_assigned_ip_leases WHERE user_id=%s ORDER BY lease_id", (int(user_id),)).fetchall()
        return tuple((str(ip),str(status),ras,session) for ip,status,ras,session in rows)
