"""A1.24-compatible Access-Request IP-pool allocation."""
from __future__ import annotations
from dataclasses import dataclass
from .aaa import AAAAction, AAAResult
from .ip_pool import IPPoolFullError, IPPoolRuntimeRegistry

@dataclass(frozen=True, slots=True)
class IPPoolAllocationPolicy:
    """Allocate the first free address from RAS-bound native IP pools."""
    registry: IPPoolRuntimeRegistry

    def evaluate(self, request):
        if request.attributes.get("Framed-IP-Address") not in (None, ""):
            return None
        if str(request.attributes.get("__ras_ip_assignment", "1")) == "0":
            return None
        raw_pool_ids = request.attributes.get("__ras_ippool_ids", "")
        if not raw_pool_ids:
            return None
        pool_ids = []
        for raw_id in str(raw_pool_ids).split(","):
            raw_id = raw_id.strip()
            if raw_id:
                pool_ids.append(int(raw_id))
        for pool_id in pool_ids:
            try:
                address = self.registry.allocate(pool_id)
            except IPPoolFullError:
                continue
            return AAAResult(
                AAAAction.ACCEPT,
                {"Framed-IP-Address": address, "Framed-IP-Netmask": "255.255.255.255"},
            )
        return AAAResult(AAAAction.REJECT, reason="IP_POOL_EXHAUSTED")
