"""PostgreSQL mapping for the native A1.24 ippool tables."""
from typing import ClassVar, Protocol
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class IPLease:
    pool_id: int
    address: str
    user_id: int | None = None

class IPPoolRepository(Protocol):
    def list_addresses(self, pool_id: int) -> tuple[str, ...]: ...
    def add_address(self, pool_id: int, address: str) -> None: ...
    def remove_address(self, pool_id: int, address: str) -> None: ...

class IPPoolSql:
    list_addresses: ClassVar[str] = "SELECT ip::text FROM ippool_ips WHERE ippool_id=%s ORDER BY ip"
    add_address: ClassVar[str] = "INSERT INTO ippool_ips(ippool_id,ip) VALUES (%s,%s::inet)"
    remove_address: ClassVar[str] = "DELETE FROM ippool_ips WHERE ippool_id=%s AND ip=%s::inet"
    pool: ClassVar[str] = "SELECT ippool_id,ippool_name,ippool_comment FROM ippool WHERE ippool_id=%s"
