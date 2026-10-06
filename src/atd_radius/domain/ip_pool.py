"""IP pool primitives matching A1.24's ordered free/used container semantics."""
from __future__ import annotations
from dataclasses import dataclass,field
import ipaddress
from typing import Iterable

class IPPoolError(ValueError): pass

@dataclass(slots=True)
class IPPool:
    name:str
    addresses_list:list[ipaddress.IPv4Address]
    enabled:bool=True
    used:list[ipaddress.IPv4Address]=field(default_factory=list)
    @classmethod
    def from_cidr(cls,name:str,cidr:str,enabled:bool=True)->"IPPool":
        network=ipaddress.ip_network(cidr,strict=True)
        if not isinstance(network,ipaddress.IPv4Network): raise IPPoolError("IPv4 only")
        return cls(name,list(network.hosts()),enabled)
    def free(self)->list[ipaddress.IPv4Address]: return [ip for ip in self.addresses_list if ip not in self.used]
    def allocate(self)->ipaddress.IPv4Address:
        if not self.enabled: raise IPPoolError(f"IP pool {self.name!r} is disabled")
        free=self.free()
        if not free: raise IPPoolError(f"IP pool {self.name!r} is exhausted")
        ip=free[0]; self.used.append(ip); return ip
    def use(self,address:str|ipaddress.IPv4Address)->ipaddress.IPv4Address:
        ip=ipaddress.ip_address(address)
        if not isinstance(ip,ipaddress.IPv4Address) or ip not in self.addresses_list: raise IPPoolError("IP is not in pool")
        if ip in self.used: raise IPPoolError("IP is already in use")
        self.used.append(ip); return ip
    def release(self,address:str|ipaddress.IPv4Address)->None:
        ip=ipaddress.ip_address(address)
        try: self.used.remove(ip)
        except ValueError: raise IPPoolError("IP is not in used pool")
    def set_in_reply(self,reply:dict[str,str])->ipaddress.IPv4Address:
        ip=self.allocate(); reply["Framed-IP-Address"]=str(ip); reply["Framed-IP-Netmask"]="255.255.255.255"; return ip
    def is_available(self,address:str|ipaddress.IPv4Address)->bool:
        ip=ipaddress.ip_address(address); return ip in self.addresses_list and ip not in self.used

class IPAllocator:
    """Compatibility adapter for the original ATD allocator API."""
    def __init__(self,pool:IPPool): self.pool=pool
    def allocate(self,used:Iterable[str|ipaddress.IPv4Address])->ipaddress.IPv4Address:
        used_set={ipaddress.ip_address(x) for x in used}
        for ip in self.pool.addresses_list:
            if ip not in used_set: return ip
        raise IPPoolError(f"IP pool {self.pool.name!r} is exhausted")
    def is_available(self,address:str|ipaddress.IPv4Address,used:Iterable[str|ipaddress.IPv4Address])->bool:
        ip=ipaddress.ip_address(address); return ip in self.pool.addresses_list and ip not in {ipaddress.ip_address(x) for x in used}



class IPPoolFullError(IPPoolError):
    pass


class IPPoolIPNotInUseError(IPPoolError):
    pass


class IPPoolIPNotInPoolError(IPPoolError):
    pass


class IPPoolRuntime:
    """A1.24-compatible process-local free/used IP container."""

    def __init__(self, pool_id: int, name: str, comment: str | None, addresses) -> None:
        self.pool_id = pool_id
        self.name = name
        self.comment = comment
        import threading
        self._lock = threading.RLock()
        self._all_ips = tuple(addresses)
        self._free = list(self._all_ips)
        self._used: list[str] = []

    @property
    def all_ips(self) -> tuple[str, ...]:
        with self._lock:
            return self._all_ips

    @property
    def free_ips(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._free)

    @property
    def used_ips(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._used)

    def allocate(self) -> str:
        with self._lock:
            if not self._free:
                raise IPPoolFullError(f"IP pool {self.name} has no free addresses")
            ip = self._free.pop(0)
            self._used.append(ip)
            return ip

    def claim(self, ip: str) -> None:
        with self._lock:
            if ip not in self._all_ips:
                raise IPPoolIPNotInPoolError(f"IP address {ip} is not a member of pool {self.name}")
            if ip not in self._free:
                raise IPPoolFullError(f"IP address {ip} is already in use")
            self._free.remove(ip)
            self._used.append(ip)

    def release(self, ip: str) -> None:
        with self._lock:
            try:
                self._used.remove(ip)
            except ValueError as exc:
                raise IPPoolIPNotInUseError(f"IP address {ip} is not in use") from exc
            if ip in self._all_ips:
                self._free.append(ip)

    def reload(self, addresses) -> None:
        with self._lock:
            new_all = tuple(addresses)
            used = [ip for ip in self._used if ip in new_all]
            used_set = set(used)
            self._all_ips = new_all
            self._used = used
            self._free = [ip for ip in new_all if ip not in used_set]


class IPPoolRuntimeRegistry:
    """Load native ippool membership and expose A1.24 allocation operations."""

    def __init__(self, repository) -> None:
        self.repository = repository
        import threading
        self._pools = {}
        self._lock = threading.RLock()

    def reload(self, pool_id: int | None = None):
        with self._lock:
            if pool_id is None:
                records = self.repository.list()
                existing = self._pools
                self._pools = {}
                for record in records:
                    addresses = self.repository.list_addresses(record.pool_id)
                    pool = existing.get(record.pool_id)
                    if pool is None:
                        pool = IPPoolRuntime(record.pool_id, record.name, record.comment, addresses)
                    else:
                        pool.name = record.name
                        pool.comment = record.comment
                        pool.reload(addresses)
                    self._pools[record.pool_id] = pool
            else:
                record = self.repository.get(pool_id)
                if record is None:
                    self._pools.pop(pool_id, None)
                else:
                    addresses = self.repository.list_addresses(pool_id)
                    pool = self._pools.get(pool_id)
                    if pool is None:
                        pool = IPPoolRuntime(record.pool_id, record.name, record.comment, addresses)
                        self._pools[pool_id] = pool
                    else:
                        pool.name = record.name
                        pool.comment = record.comment
                        pool.reload(addresses)
            return self.active()

    def get(self, pool_id: int) -> IPPoolRuntime | None:
        return self._pools.get(pool_id)

    def get_by_name(self, name: str) -> IPPoolRuntime | None:
        return next((pool for pool in self._pools.values() if pool.name == name), None)

    def allocate(self, pool_id: int) -> str:
        return self._require(pool_id).allocate()

    def claim(self, pool_id: int, ip: str) -> None:
        self._require(pool_id).claim(ip)

    def release(self, pool_id: int, ip: str) -> None:
        self._require(pool_id).release(ip)

    def find_pool(self, pool_ids, ip: str) -> int | None:
        for pool_id in pool_ids:
            pool = self._pools.get(int(pool_id))
            if pool is not None and ip in pool.all_ips:
                return int(pool_id)
        return None

    def ensure_claimed(self, pool_id: int, ip: str) -> None:
        pool = self._require(pool_id)
        if ip in pool.used_ips:
            return
        pool.claim(ip)

    def active(self):
        return tuple(self._pools[key] for key in sorted(self._pools))

    def snapshot(self):
        return dict(self._pools)

    def _require(self, pool_id: int) -> IPPoolRuntime:
        pool = self._pools.get(pool_id)
        if pool is None:
            raise KeyError(f"IP pool {pool_id} is not loaded")
        return pool
