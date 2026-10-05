"""Session admission and timeout policies derived from IBSng attributes."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from typing import Iterable
from .models import AttributeSet

class SessionAdmissionReason(str):
    LOCKED="locked"; MULTI_LOGIN="multi_login"

@dataclass(frozen=True,slots=True)
class ActiveSessionView:
    unique_id:str
    started_at:datetime|None=None

@dataclass(frozen=True,slots=True)
class SessionPolicyDecision:
    allowed:bool
    reason:str|None=None
    session_timeout_seconds:int|None=None
    idle_timeout_seconds:int|None=None

def _positive_int(attributes:AttributeSet,name:str)->int|None:
    value=attributes.get(name)
    if value in (None,"",0,"0"): return None
    try: parsed=int(value)
    except (TypeError,ValueError): return None
    return parsed if parsed>0 else None

def session_policy(attributes:AttributeSet,active_sessions:Iterable[ActiveSessionView]=())->SessionPolicyDecision:
    if "lock" in attributes.values:
        return SessionPolicyDecision(False,SessionAdmissionReason.LOCKED)
    sessions=list(active_sessions)
    # A1.24 MultiLogin initializes to 1 when the attribute is absent.
    multi_login=attributes.get("multi_login",1)
    if isinstance(multi_login,bool): limit=1 if multi_login else 0
    else:
        try: limit=int(multi_login)
        except (TypeError,ValueError): limit=1
    if len(sessions)>=limit:
        return SessionPolicyDecision(False,SessionAdmissionReason.MULTI_LOGIN)
    return SessionPolicyDecision(True,session_timeout_seconds=_positive_int(attributes,"session_timeout"),idle_timeout_seconds=_positive_int(attributes,"idle_timeout"))

def session_deadline(started_at:datetime,timeout_seconds:int|None)->datetime|None:
    return None if timeout_seconds is None else started_at+timedelta(seconds=timeout_seconds)
