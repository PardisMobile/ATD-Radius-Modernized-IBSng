"""IBSng A1.24-compatible user policy adapters."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .aaa import AAAAction,AAARequest,AAAResult
from .session_policy import ActiveSessionView,session_policy

def _attrs(request):
    from .models import AttributeSet
    return AttributeSet(request.attributes)

@dataclass(frozen=True,slots=True)
class LockPolicy:
    def evaluate(self,request):
        if str(request.attributes.get("lock","")).lower() in {"1","true","yes","on","locked"}:
            return AAAResult(AAAAction.REJECT,reason="USER_LOCKED")
        return None

@dataclass(frozen=True,slots=True)
class MultiLoginPolicy:
    active_sessions: tuple[ActiveSessionView,...]=()
    def evaluate(self,request):
        d=session_policy(_attrs(request),self.active_sessions)
        return AAAResult(AAAAction.REJECT,reason="MAX_CONCURRENT") if not d.allowed and d.reason=="multi_login" else None

@dataclass(frozen=True,slots=True)
class TimeoutPolicy:
    def evaluate(self,request):
        d=session_policy(_attrs(request))
        out={}
        if d.session_timeout_seconds is not None: out["Session-Timeout"]=str(d.session_timeout_seconds)
        if d.idle_timeout_seconds is not None: out["Idle-Timeout"]=str(d.idle_timeout_seconds)
        return AAAResult(AAAAction.ACCEPT,out) if out else None

@dataclass(frozen=True,slots=True)
class AbsoluteExpiryPolicy:
    now: datetime
    def evaluate(self,request):
        raw=request.attributes.get("abs_exp_date")
        if raw in (None,""): return None
        try: expiry=float(raw)
        except (TypeError,ValueError): return None
        now=self.now.timestamp()
        if now>=expiry: return AAAResult(AAAAction.REJECT,reason="ABS_EXP_DATE_REACHED")
        return AAAResult(AAAAction.ACCEPT,{"Session-Timeout":str(max(0,int(expiry-now)))})

@dataclass(frozen=True,slots=True)
class RelativeExpiryPolicy:
    """A1.24 rel_exp: first successful login establishes first_login."""
    now: datetime
    def evaluate(self,request):
        raw=request.attributes.get("rel_exp_date")
        if raw in (None,""): return None
        try: duration=float(raw)
        except (TypeError,ValueError): return None
        first=request.attributes.get("first_login")
        if first in (None,""):
            return AAAResult(AAAAction.ACCEPT,{"first_login":str(int(self.now.timestamp()))})
        try: deadline=float(first)+duration
        except (TypeError,ValueError): return None
        remaining=deadline-self.now.timestamp()
        if remaining<=0: return AAAResult(AAAAction.REJECT,reason="REL_EXP_DATE_REACHED")
        return AAAResult(AAAAction.ACCEPT,{"Session-Timeout":str(int(remaining))})
