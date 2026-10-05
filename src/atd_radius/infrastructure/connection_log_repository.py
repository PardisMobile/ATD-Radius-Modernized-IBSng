"""PostgreSQL SQL contract for A1.24 connection_log."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True,slots=True)
class ConnectionLogSql:
    insert_function:str = """SELECT insert_connection_log(%s::bigint,%s::numeric,%s::timestamp,%s::timestamp,%s::boolean,%s::smallint,%s::integer,%s::text[],%s::text[])"""
    delete_details_for_users:str = """DELETE FROM connection_log_details WHERE connection_log_id IN (SELECT connection_log_id FROM connection_log WHERE user_id = ANY(%s))"""
    delete_logs_for_users:str = """DELETE FROM connection_log WHERE user_id = ANY(%s)"""
    insert_detail:str = """INSERT INTO connection_log_details(connection_log_id,name,value) VALUES (%s,%s,%s)"""
    close:str = """UPDATE connection_log SET logout_time=%s, credit_used=%s, successful=%s WHERE connection_log_id=%s"""
