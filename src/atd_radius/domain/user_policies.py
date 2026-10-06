"""IBSng A1.24-compatible user policy adapters."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .aaa import AAAAction,AAAResult
from .session_policy import ActiveSessionView,session_policy
from .ras_provider import provider_multi_login

@dataclass(frozen=True,slots=True)
class AuthenticationPolicy:
    """Reject users that cannot be authenticated against native credentials."""
    def evaluate(self,request):
        if request.attributes.get("__user_found") != "1" or request.attributes.get("__password_ok") != "1":
            return AAAResult(AAAAction.REJECT,reason="INVALID_CREDENTIALS")
        method = request.attributes.get("__auth_method")
        if method == "mschapv1":
            key = request.attributes.get("__mschapv1_mppe_key")
            if key:
                return AAAResult(
                    AAAAction.ACCEPT,
                    {
                        "MS-CHAP-MPPE-Keys": key,
                        "MS-MPPE-Encryption-Policy": "00000001",
                        "MS-MPPE-Encryption-Types": "00000006",
                    },
                )
        if method == "mschapv2":
            success = request.attributes.get("__mschapv2_success")
            send_key = request.attributes.get("__mschapv2_send_key")
            recv_key = request.attributes.get("__mschapv2_recv_key")
            if success and send_key and recv_key:
                return AAAResult(
                    AAAAction.ACCEPT,
                    {
                        "MS-CHAP2-Success": success,
                        "MS-MPPE-Send-Key": send_key,
                        "MS-MPPE-Recv-Key": recv_key,
                        "MS-MPPE-Encryption-Policy": "00000001",
                        "MS-MPPE-Encryption-Types": "00000006",
                    },
                )
            if success:
                return AAAResult(AAAAction.ACCEPT, {"MS-CHAP2-Success": success})
        return None


def _int_attr(attributes, name, default):
    raw = attributes.get(name, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default

def ras_allows_multi_login(ras_type, ras_attributes=None, service="internet"):
    attrs = ras_attributes or {}
    if service == "voip":
        if rtype == "gnugk":
            return _int_attr(attrs, "gnugk_multiple_login", 0) != 0
        if rtype == "asterisk":
            return _int_attr(attrs, "asterisk_multi_login", 0) != 0
    explicit = provider_multi_login(ras_type, service)
    if explicit is not None:
        return explicit
    return True
def _attrs(request):
    from .models import AttributeSet
    return AttributeSet(request.attributes)

@dataclass(frozen=True,slots=True)
class LockPolicy:
    def evaluate(self,request):
        if "lock" in request.attributes:
            return AAAResult(AAAAction.REJECT,reason="USER_LOCKED")
        return None

@dataclass(frozen=True,slots=True)
class MultiLoginPolicy:
    active_sessions: tuple[ActiveSessionView,...]=()
    active_sessions_provider: object | None = None
    def evaluate(self,request):
        sessions = self.active_sessions
        if self.active_sessions_provider is not None:
            user_id = request.attributes.get("__user_id")
            if user_id not in (None, ""):
                sessions = tuple(self.active_sessions_provider(int(user_id)))
        # IBSng increments instances before USER_LOGIN hooks: evaluate the
        # user limit first, then the RAS capability for an additional session.
        d=session_policy(_attrs(request),sessions)
        if not d.allowed and d.reason=="multi_login":
            return AAAResult(AAAAction.REJECT,reason="MAX_CONCURRENT")
        ras_multi_login = request.attributes.get("__ras_multi_login_allowed",
            request.attributes.get("ras_multi_login"))
        if ras_multi_login in (False, "0", "false", "False") and len(sessions) > 0:
            return AAAResult(AAAAction.REJECT, reason="RAS_DOESNT_ALLOW_MULTILOGIN")
        return None

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
    now: datetime
    def evaluate(self,request):
        raw=request.attributes.get("rel_exp_date")
        if raw in (None,""): return None
        try: duration=float(raw)
        except (TypeError,ValueError): return None
        first=request.attributes.get("first_login")
        if first in (None,""): return AAAResult(AAAAction.ACCEPT,{"first_login":str(int(self.now.timestamp()))})
        try: deadline=float(first)+duration
        except (TypeError,ValueError): return None
        remaining=deadline-self.now.timestamp()
        if remaining<=0: return AAAResult(AAAAction.REJECT,reason="REL_EXP_DATE_REACHED")
        return AAAResult(AAAAction.ACCEPT,{"Session-Timeout":str(int(remaining))})
