"""RFC 5176 session selection and control over the runtime session registry."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from .radius_runtime import SessionRegistry

ERROR_UNSUPPORTED_ATTRIBUTE="401"
ERROR_MISSING_ATTRIBUTE="402"
ERROR_SESSION_NOT_FOUND="503"

NAS_IDENTIFIERS={"NAS-IP-Address","NAS-Identifier"}
SESSION_IDENTIFIERS={"User-Name","NAS-Port","Framed-IP-Address","Called-Station-Id","Calling-Station-Id","Acct-Session-Id","Acct-Multi-Session-Id","NAS-Port-Id","Chargeable-User-Identity"}
COMMON_ALLOWED=NAS_IDENTIFIERS|SESSION_IDENTIFIERS|{"Message-Authenticator","Proxy-State"}
DISCONNECT_ALLOWED=COMMON_ALLOWED
COA_ALLOWED=COMMON_ALLOWED|{"Filter-Id","NAS-Filter-Rule","Service-Type","State"}

@dataclass(frozen=True,slots=True)
class ControlResult:
    ok:bool
    error_cause:str|None=None

@dataclass(slots=True)
class RegistrySessionControl:
    registry:SessionRegistry
    def _select(self,attributes:Mapping[str,str],allowed:set[str]):
        if set(attributes)-allowed: return (),ERROR_UNSUPPORTED_ATTRIBUTE
        if not any(name in attributes for name in SESSION_IDENTIFIERS): return (),ERROR_MISSING_ATTRIBUTE
        matches=self.registry.matching(attributes)
        if not matches: return (),ERROR_SESSION_NOT_FOUND
        return matches,None
    def disconnect(self,attributes:Mapping[str,str])->ControlResult:
        matches,error=self._select(attributes,DISCONNECT_ALLOWED)
        if error: return ControlResult(False,error)
        for state in matches: state.stopped=True
        return ControlResult(True)
    def change_of_authorization(self,attributes:Mapping[str,str])->ControlResult:
        matches,error=self._select(attributes,COA_ALLOWED)
        if error: return ControlResult(False,error)
        changes={name:value for name,value in attributes.items() if name in {"Filter-Id","NAS-Filter-Rule"}}
        if not changes: return ControlResult(False,ERROR_MISSING_ATTRIBUTE)
        for state in matches: state.attributes={**state.attributes,**changes}
        return ControlResult(True)
