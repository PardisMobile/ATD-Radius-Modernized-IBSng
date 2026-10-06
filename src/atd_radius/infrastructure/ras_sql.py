"""Parameterized SQL contracts for the A1.24 RAS persistence boundary."""
from __future__ import annotations

RAS_COLUMNS = (
    "ras_id", "ras_description", "ras_ip", "ras_type",
    "radius_secret", "active", "comment",
)

def select_ras(ras_id: int) -> str:
    return ("SELECT ras_id, ras_description, ras_ip, ras_type, radius_secret, active, comment "
            "FROM ras WHERE ras_id = %s")

def select_active_ras_ids() -> str:
    return "SELECT ras_id FROM ras WHERE active = TRUE ORDER BY ras_id"

def select_ras_ports(ras_id: int) -> str:
    return ("SELECT ras_id, port_name, phone, type, comment FROM ras_ports "
            "WHERE ras_id = %s ORDER BY port_name")

def select_ras_ippools(ras_id: int) -> str:
    return "SELECT serial, ras_id, ippool_id FROM ras_ippools WHERE ras_id = %s ORDER BY serial"

def upsert_ras_port() -> str:
    return ("INSERT INTO ras_ports (ras_id, port_name, phone, type, comment) VALUES (%s,%s,%s,%s,%s) "
            "ON CONFLICT (ras_id, port_name) DO UPDATE SET phone=EXCLUDED.phone, type=EXCLUDED.type, comment=EXCLUDED.comment")

def delete_ras_port() -> str:
    return "DELETE FROM ras_ports WHERE ras_id = %s AND port_name = %s"

def insert_ras_ippool() -> str:
    return "INSERT INTO ras_ippools (ras_id, ippool_id) VALUES (%s, %s) RETURNING serial"

def delete_ras_ippool() -> str:
    return "DELETE FROM ras_ippools WHERE serial = %s"
