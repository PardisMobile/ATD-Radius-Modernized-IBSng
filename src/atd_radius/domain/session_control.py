"""Session control operations for Disconnect and CoA boundaries."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from .radius_runtime import SessionRegistry

@dataclass(slots=True)
class RegistrySessionControl:
    registry:SessionRegistry
    def disconnect(self,attributes:Mapping[str,str])->bool:
        key=self._find(attributes)
        if key is None: return False
        self.registry.stop(key); return True
    def change_of_authorization(self,attributes:Mapping[str,str])->bool:
        key=self._find(attributes)
        if key is None: return False
        state=self.registry.get(key)
        if state is None or state.stopped: return False
        state.attributes={**state.attributes,**dict(attributes)}
        return True
    def _find(self,attributes):
        sid=attributes.get("Acct-Session-Id")
        if not sid: return None
        for state in self.registry._sessions.values():
            if state.key.unique_id==sid: return state.key
        return None
