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
        # CIDR convenience; explicit list remains authoritative for allocation order.
        return cls(name,list(network.hosts()),enabled)

    @property
    def network(self): return ipaddress.ip_network(f"{self.addresses_list[0]}/{len(self.addresses_list)}",strict=False) if self.addresses_list else None

    def free(self)->list[ipaddress.IPv4Address]:
        return [ip for ip in self.addresses_list if ip not in self.used]

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
        ip=self.allocate()
        reply["Framed-IP-Address"]=str(ip); reply["Framed-IP-Netmask"]="255.255.255.255"
        return ip

    def is_available(self,address:str|ipaddress.IPv4Address)->bool:
        ip=ipaddress.ip_address(address)
        return ip in self.addresses_list and ip not in self.used
