"""IBSng A1.24-compatible user policy adapters."""
from __future__ import annotations
from dataclasses import dataclass
import ipaddress
from datetime import datetime, timezone
from .aaa import AAAAction,AAAResult
from .session_policy import ActiveSessionView,session_policy
from .ras_provider import normalize_ras_type, provider_multi_login

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
    rtype = normalize_ras_type(ras_type)
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
        # A1.24 increments instances before USER_LOGIN hooks and checks the
        # configured user limit before the accumulated RAS capability list.
        raw_ras_multi_login = request.attributes.get(
            "__ras_multi_login_allowed", request.attributes.get("ras_multi_login")
        )
        current_ras_allowed = None
        if raw_ras_multi_login is not None:
            current_ras_allowed = not (
                raw_ras_multi_login is False
                or str(raw_ras_multi_login).strip().lower() in {"0", "false"}
            )
        decision = session_policy(
            _attrs(request),
            sessions,
            current_ras_multi_login_allowed=current_ras_allowed,
        )
        if not decision.allowed:
            reason = {
                "multi_login": "MAX_CONCURRENT",
                "ras_doesnt_allow_multilogin": "RAS_DOESNT_ALLOW_MULTILOGIN",
            }.get(decision.reason, decision.reason or "POLICY_REJECTED")
            return AAAResult(AAAAction.REJECT, reason=reason)
        return None

@dataclass(frozen=True, slots=True)
class LimitMacPolicy:
    """Mirror A1.24 limit_mac.s_login: enforce only when the RAS supplies mac."""
    def evaluate(self, request):
        allowed = request.attributes.get("limit_mac")
        mac = request.attributes.get("mac")
        if allowed in (None, "") or mac in (None, ""):
            return None
        permitted = str(allowed).split(",")
        if str(mac) not in permitted:
            return AAAResult(AAAAction.REJECT, reason="LOGIN_FROM_THIS_MAC_DENIED")
        return None


@dataclass(frozen=True, slots=True)
class LimitStationIPPolicy:
    """Mirror A1.24 limit_station_ip.s_login with IPy-compatible subnet membership."""
    def evaluate(self, request):
        configured = request.attributes.get("limit_station_ip")
        station_ip = request.attributes.get("station_ip")
        if configured in (None, "") or station_ip in (None, ""):
            return None
        try:
            address = ipaddress.ip_address(str(station_ip).strip())
        except ValueError:
            return AAAResult(AAAAction.REJECT, reason="LOGIN_FROM_THIS_IP_DENIED")
        for entry in str(configured).split(","):
            try:
                network = ipaddress.ip_network(entry.strip(), strict=False)
            except ValueError:
                # Invalid stored policy must never become an allow-all rule.
                return AAAResult(AAAAction.REJECT, reason="LOGIN_FROM_THIS_IP_DENIED")
            if address.version == network.version and address in network:
                return None
        return AAAResult(AAAAction.REJECT, reason="LOGIN_FROM_THIS_IP_DENIED")


@dataclass(frozen=True,slots=True)
class TimeoutPolicy:
    def evaluate(self,request):
        d=session_policy(_attrs(request))
        out={}
        if d.session_timeout_seconds is not None:
            # Expiration policies may already have emitted a shorter remaining
            # lifetime. Never extend that lifetime with the configured timeout.
            existing = request.attributes.get("Session-Timeout")
            try:
                configured = int(existing) if existing not in (None, "") else None
            except (TypeError, ValueError):
                configured = None
            timeout = d.session_timeout_seconds
            if configured is not None:
                timeout = min(timeout, configured)
            out["Session-Timeout"] = str(timeout)
        if d.idle_timeout_seconds is not None: out["Idle-Timeout"]=str(d.idle_timeout_seconds)
        return AAAResult(AAAAction.ACCEPT,out) if out else None

@dataclass(frozen=True,slots=True)
class AbsoluteExpiryPolicy:
    now: datetime | None = None
    def evaluate(self,request):
        raw=request.attributes.get("abs_exp_date")
        if raw in (None,""): return None
        try: expiry=float(raw)
        except (TypeError,ValueError): return None
        now=(self.now or datetime.now(timezone.utc)).timestamp()
        if now>=expiry: return AAAResult(AAAAction.REJECT,reason="ABS_EXP_DATE_REACHED")
        return AAAResult(AAAAction.ACCEPT,{"Session-Timeout":str(max(0,int(expiry-now)))})

@dataclass(frozen=True,slots=True)
class RelativeExpiryPolicy:
    now: datetime | None = None
    def evaluate(self,request):
        raw=request.attributes.get("rel_exp_date")
        if raw in (None,""): return None
        try: duration=float(raw)
        except (TypeError,ValueError): return None
        first=request.attributes.get("first_login")
        if first in (None, ""):
            first=request.attributes.get("__first_login_candidate")
        if first in (None,""): return None
        try: deadline=float(first)+duration
        except (TypeError,ValueError): return None
        now=(self.now or datetime.now(timezone.utc)).timestamp()
        remaining=deadline-now
        if remaining<=0: return AAAResult(AAAAction.REJECT,reason="REL_EXP_DATE_REACHED")
        remaining_seconds = int(remaining)
        existing_timeout = request.attributes.get("Session-Timeout")
        try:
            if existing_timeout not in (None, ""):
                remaining_seconds = min(remaining_seconds, int(existing_timeout))
        except (TypeError, ValueError):
            pass
        return AAAResult(AAAAction.ACCEPT,{"Session-Timeout":str(remaining_seconds)})
