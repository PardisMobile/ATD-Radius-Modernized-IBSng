"""Compatibility facade for the native A1.24 in-memory IP pool runtime.

A1.24 stores pool membership in ippool/ippool_ips and tracks used/free
addresses in the running process. The modern implementation therefore does
not create an invented ip_allocations schema.
"""
from atd_radius.domain.ip_pool import (
    IPPoolFullError,
    IPPoolIPNotInUseError,
    IPPoolIPNotInPoolError,
    IPPoolRuntime,
    IPPoolRuntimeRegistry,
)

__all__ = [
    "IPPoolFullError",
    "IPPoolIPNotInUseError",
    "IPPoolIPNotInPoolError",
    "IPPoolRuntime",
    "IPPoolRuntimeRegistry",
]
