from types import SimpleNamespace

import pytest

from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_codec import decode, encode_response
from atd_radius.domain.radius_runtime import SessionKey, SessionState
from atd_radius.domain.ras import RAS
from atd_radius.infrastructure.ras_termination import (
    PermanentRASTerminationError,
    RASTerminationError,
    SourceRASDisconnectClient,
    UnsupportedRASTermination,
)


class FakeSocket:
    def __init__(self, secret, response_code=RadiusCode.DISCONNECT_ACK, source_override=None, zero_response_authenticator=False):
        self.secret = secret
        self.response_code = response_code
        self.source_override = source_override
        self.zero_response_authenticator = zero_response_authenticator
        self.target = None
        self.timeout = None
        self.request = None
        self.response = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, timeout):
        self.timeout = timeout

    def sendto(self, wire, target):
        self.target = target
        self.request = decode(wire, self.secret)
        response = RadiusPacket(
            self.response_code,
            self.request.identifier,
            {},
            self.request.authenticator,
        )
        self.response = encode_response(response, self.request, self.secret)
        if self.zero_response_authenticator:
            self.response = self.response[:4] + bytes(16) + self.response[20:]

    def recvfrom(self, _maximum):
        return self.response, self.source_override or self.target


def make_ras(kind, *, ip="192.0.2.10", attributes=None):
    return RAS(
        ras_id=3,
        ip=ip,
        description="test RAS",
        ras_type=kind,
        radius_secret="shared-secret",
        attributes=attributes or {},
    )


def make_session(unique_id="call-1", attrs=None):
    return SessionState(
        SessionKey(7, 3, unique_id),
        attributes=attrs if attrs is not None else {"User-Name": "alice"},
        started=True,
    )


def test_chillispot_termination_uses_source_configured_endpoint_and_username():
    holder = {}
    def socket_factory(*_args):
        holder["socket"] = FakeSocket("shared-secret")
        return holder["socket"]

    ras = make_ras(
        "ChilliSpot",
        attributes={
            "chilli_spot_disconnect_ip": "192.0.2.44",
            "chilli_spot_disconnect_port": "3799",
            "chilli_spot_radius_timeout": "3",
        },
    )
    SourceRASDisconnectClient(socket_factory=socket_factory, identifier_factory=lambda: 17).terminate(
        ras, make_session(), "credit_finished"
    )

    fake = holder["socket"]
    assert fake.target == ("192.0.2.44", 3799)
    assert fake.timeout == 3
    assert fake.request.code is RadiusCode.DISCONNECT_REQUEST
    assert fake.request.identifier == 17
    assert fake.request.attributes == {"User-Name": "alice"}


def test_mvts_termination_includes_source_h323_conf_id_vsa():
    holder = {}
    def socket_factory(*_args):
        holder["socket"] = FakeSocket("shared-secret")
        return holder["socket"]

    ras = make_ras("MVTS", attributes={"mvts_radius_auth_port": "1812", "mvts_radius_timeout": "4"})
    SourceRASDisconnectClient(socket_factory=socket_factory, identifier_factory=lambda: 19).terminate(
        ras, make_session("conf-123"), "no_effective_rule"
    )

    fake = holder["socket"]
    assert fake.target == ("192.0.2.10", 1812)
    assert fake.timeout == 4
    assert fake.request.attributes == {
        "User-Name": "alice",
        "H323-conf-id": "h323-conf-id=conf-123",
    }


def test_disconnect_rejection_is_not_reported_as_success():
    holder = {}
    def socket_factory(*_args):
        holder["socket"] = FakeSocket("shared-secret", RadiusCode.DISCONNECT_NAK)
        return holder["socket"]

    with pytest.raises(RASTerminationError, match="rejected Disconnect-Request"):
        SourceRASDisconnectClient(socket_factory=socket_factory).terminate(
            make_ras("MVTS"), make_session(), "credit_finished"
        )


def test_disconnect_response_from_unexpected_endpoint_is_rejected():
    holder = {}
    def socket_factory(*_args):
        holder["socket"] = FakeSocket(
            "shared-secret", source_override=("198.51.100.8", 1812)
        )
        return holder["socket"]

    with pytest.raises(RASTerminationError, match="unexpected endpoint"):
        SourceRASDisconnectClient(socket_factory=socket_factory).terminate(
            make_ras("MVTS"), make_session(), "credit_finished"
        )


def test_unsupported_provider_fails_closed_without_sending_packets():
    called = []
    client = SourceRASDisconnectClient(socket_factory=lambda *_args: called.append(True))
    with pytest.raises(UnsupportedRASTermination):
        client.terminate(make_ras("Mikrotik"), make_session(), "credit_finished")
    assert called == []


def test_termination_requires_user_name():
    with pytest.raises(RASTerminationError, match="User-Name"):
        SourceRASDisconnectClient(socket_factory=lambda *_args: None).terminate(
            make_ras("ChilliSpot"), make_session(attrs={}), "credit_finished"
        )


def test_mvts_zero_filled_response_authenticator_matches_a124_exception():
    holder = {}
    def socket_factory(*_args):
        holder["socket"] = FakeSocket("shared-secret", zero_response_authenticator=True)
        return holder["socket"]

    SourceRASDisconnectClient(socket_factory=socket_factory).terminate(
        make_ras("MVTS"), make_session(), "credit_finished"
    )


def test_chillispot_still_requires_valid_response_authenticator():
    def socket_factory(*_args):
        return FakeSocket("shared-secret", zero_response_authenticator=True)

    with pytest.raises(RASTerminationError, match="authenticator is invalid"):
        SourceRASDisconnectClient(socket_factory=socket_factory).terminate(
            make_ras("ChilliSpot"), make_session(), "credit_finished"
        )


_DEFAULT_EXTERNAL_RESULT = object()


class FakeExternalTerminationService:
    def __init__(self, result=_DEFAULT_EXTERNAL_RESULT):
        if result is _DEFAULT_EXTERNAL_RESULT:
            result = (SimpleNamespace(error_status=0),)
        self.result = result
        self.calls = []

    def disconnect_cisco(self, **kwargs):
        self.calls.append(("cisco", kwargs))
        return self.result

    def disconnect_mikrotik(self, **kwargs):
        self.calls.append(("mikrotik", kwargs))
        return self.result

    def disconnect_cisco_vpdn(self, **kwargs):
        self.calls.append(("cisco_vpdn", kwargs))
        return self.result

    def execute_request(self, request, **kwargs):
        self.calls.append((request.provider, request))
        return self.result


@pytest.mark.parametrize(
    ("provider", "unique_id", "expected_provider"),
    [("PortMaster", "7", "portmaster"), ("Total Control", "42", "total_control")],
)
def test_source_snmp_termination_adapters_are_wired_into_voip_kill_path(provider, unique_id, expected_provider):
    external = FakeExternalTerminationService()
    client = SourceRASDisconnectClient(external_service=external)
    ras = make_ras(provider)
    session = make_session(unique_id=unique_id)
    client.terminate(ras, session, "credit_finished")
    assert len(external.calls) == 1
    name, request = external.calls[0]
    assert name == expected_provider
    assert request.parameters["ras_ip"] == ras.ip


def test_cisco_termination_uses_source_configured_snmp_branch():
    external = FakeExternalTerminationService(result={"disconnected": True})
    client = SourceRASDisconnectClient(external_service=external)
    ras = make_ras("Cisco", attributes={
        "cisco_kill_use_snmp": "1", "cisco_snmp_community": "private",
        "cisco_snmp_timeout": "6", "cisco_snmp_retries": "2", "cisco_snmp_version": "1",
    })
    client.terminate(ras, make_session(unique_id="Async3"), "credit_finished")
    name, args = external.calls[0]
    assert name == "cisco"
    assert args["ras_ip"] == ras.ip and args["port"] == "Async3"
    assert args["kill_use_snmp"] == "1" and args["community"] == "private"
    assert args["timeout"] == 6 and args["retries"] == 2 and args["snmp_version"] == "1"


def test_cisco_rsh_unsupported_port_is_not_reported_as_success():
    external = FakeExternalTerminationService(result=None)
    client = SourceRASDisconnectClient(external_service=external)
    ras = make_ras("Cisco", attributes={"cisco_kill_use_snmp": "0", "cisco_rsh_command": "/opt/ibs/cisco/rsh_wrapper"})
    with pytest.raises(RASTerminationError, match="does not support port"):
        client.terminate(ras, make_session(unique_id="Ethernet0/1"), "credit_finished")


class FakeLauncherResult:
    def __init__(self, succeeded):
        self.succeeded = succeeded


@pytest.mark.parametrize(
    ("provider", "attribute", "command", "expected_provider"),
    [
        ("Portslave", "portslave_kill_port_command", "/opt/ibs-addons/portslave/kill", "portslave"),
        ("pppd", "pppd_kill_port_command", "/opt/ibs-addons/pppd/kill", "pppd"),
    ],
)
def test_source_launcher_termination_is_wired_to_provider_kill_command(
    provider, attribute, command, expected_provider
):
    external = FakeExternalTerminationService(result=FakeLauncherResult(True))
    ras = make_ras(provider, attributes={attribute: command})
    session = make_session(unique_id="Async7")
    SourceRASDisconnectClient(external_service=external).terminate(
        ras, session, "credit_finished"
    )

    name, request = external.calls[0]
    assert name == expected_provider
    assert request.parameters["command"] == command
    assert request.parameters["arguments"] == (ras.ip, "Async7")


@pytest.mark.parametrize(
    ("provider", "attribute", "command"),
    [
        ("Portslave", "portslave_kill_port_command", "/opt/ibs-addons/portslave/kill"),
        ("pppd", "pppd_kill_port_command", "/opt/ibs-addons/pppd/kill"),
    ],
)
def test_source_launcher_termination_failure_is_not_reported_as_success(
    provider, attribute, command
):
    external = FakeExternalTerminationService(result=FakeLauncherResult(False))
    ras = make_ras(provider, attributes={attribute: command})
    with pytest.raises(PermanentRASTerminationError, match="did not confirm successful termination"):
        SourceRASDisconnectClient(external_service=external).terminate(
            ras, make_session(unique_id="7"), "credit_finished"
        )
    assert len(external.calls) == 1


@pytest.mark.parametrize(
    ("provider", "attributes", "result"),
    [
        ("Cisco", {"cisco_kill_use_snmp": "0", "cisco_rsh_command": "/opt/ibs/cisco/rsh_wrapper"}, FakeLauncherResult(False)),
        ("Cisco", {"cisco_kill_use_snmp": "1"}, (SimpleNamespace(error_status=5),)),
        ("PortMaster", {}, (SimpleNamespace(error_status=5),)),
        ("Total Control", {}, ()),
    ],
)
def test_external_provider_termination_requires_transport_success(provider, attributes, result):
    external = FakeExternalTerminationService(result=result)
    with pytest.raises(PermanentRASTerminationError, match="did not confirm successful termination"):
        SourceRASDisconnectClient(external_service=external).terminate(
            make_ras(provider, attributes=attributes),
            make_session(unique_id="Async3" if provider == "Cisco" else "7"),
            "credit_finished",
        )


class FakeGnuGkSocket:
    def __init__(self, chunks=(b"GnuGk status;\r\n",)):
        self.chunks = list(chunks)
        self.timeout = None
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, _size):
        return self.chunks.pop(0) if self.chunks else b""

    def sendall(self, payload):
        self.sent.append(payload)


def test_gnugk_termination_uses_gated_status_port_and_voip_alias():
    holder = {}
    def factory(address, timeout):
        holder["address"] = address
        holder["factory_timeout"] = timeout
        holder["socket"] = FakeGnuGkSocket((b"Welcome ", b"status; prompt\r\n"))
        return holder["socket"]

    ras = make_ras("GnuGk", attributes={"gnugk_multiple_login": "1", "gnugk_status_port": "7001"})
    session = make_session("conf-1", {"User-Name": "login", "voip_username": "sip-alice"})
    SourceRASDisconnectClient(gnugk_socket_factory=factory).terminate(ras, session, "credit_finished")

    assert holder["address"] == (ras.ip, 7001)
    assert holder["factory_timeout"] == 5.0
    assert holder["socket"].timeout == 5.0
    assert holder["socket"].sent == [b"disconnectalias sip-alice\r\n", b"exit\r\n"]


def test_gnugk_termination_fails_closed_when_source_gate_is_disabled():
    calls = []
    client = SourceRASDisconnectClient(gnugk_socket_factory=lambda *a, **k: calls.append((a, k)))
    ras = make_ras("GnuGk", attributes={"gnugk_multiple_login": "0"})
    session = make_session(attrs={"voip_username": "sip-alice"})
    with pytest.raises(PermanentRASTerminationError, match="disabled"):
        client.terminate(ras, session, "credit_finished")
    assert calls == []


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        ({"gnugk_multiple_login": "1"}, "voip_username"),
        ({"gnugk_multiple_login": "1", "gnugk_status_port": "70000"}, "status port"),
    ],
)
def test_gnugk_termination_rejects_missing_identity_or_invalid_port(attrs, expected):
    ras = make_ras("GnuGk", attributes=attrs)
    session = make_session(attrs={"User-Name": "login"})
    with pytest.raises(PermanentRASTerminationError, match=expected):
        SourceRASDisconnectClient(gnugk_socket_factory=lambda *a, **k: None).terminate(
            ras, session, "credit_finished"
        )


def test_gnugk_termination_rejects_control_characters_in_alias():
    ras = make_ras("GnuGk", attributes={"gnugk_multiple_login": "1"})
    session = make_session(attrs={"voip_username": "alice" + chr(13) + chr(10) + "exit"})
    with pytest.raises(PermanentRASTerminationError, match="control characters"):
        SourceRASDisconnectClient(gnugk_socket_factory=lambda *a, **k: None).terminate(
            ras, session, "credit_finished"
        )


def test_gnugk_termination_requires_status_prompt_before_sending_command():
    ras = make_ras("GnuGk", attributes={"gnugk_multiple_login": "1"})
    session = make_session(attrs={"voip_username": "sip-alice"})
    fake = FakeGnuGkSocket((b"not a prompt", b""))
    with pytest.raises(RASTerminationError, match="closed before its prompt"):
        SourceRASDisconnectClient(gnugk_socket_factory=lambda *a, **k: fake).terminate(
            ras, session, "credit_finished"
        )
    assert fake.sent == []


def test_mikrotik_termination_uses_source_identity_and_nas_branch():
    external = FakeExternalTerminationService(result=FakeLauncherResult(True))
    ras = make_ras("MikroTik", attributes={"mikrotik_ssh_wrapper": "/opt/ibs-addons/mikrotik/ssh_wrapper", "mikrotik_ssh_username": "operator", "mikrotik_ssh_password": "configured-secret"})
    session = make_session("7", {"User-Name": "wire-login", "normal_username": "native-user", "Framed-IP-Address": "198.51.100.9", "NAS-Port-Type": "Wireless-802.11"})
    SourceRASDisconnectClient(external_service=external).terminate(ras, session, "credit_finished")
    name, kwargs = external.calls[0]
    assert name == "mikrotik"
    assert kwargs["username"] == "native-user" and kwargs["user_ip"] == "198.51.100.9"
    assert kwargs["nas_port_type"] == "Wireless-802.11"
    assert kwargs["ssh_wrapper"] == "/opt/ibs-addons/mikrotik/ssh_wrapper"


def test_mikrotik_termination_fails_closed_without_source_ip_or_port_type():
    external = FakeExternalTerminationService(result=FakeLauncherResult(True))
    with pytest.raises(PermanentRASTerminationError, match="session IP and NAS-Port-Type"):
        SourceRASDisconnectClient(external_service=external).terminate(ras=make_ras("MikroTik"), session=make_session(attrs={"normal_username": "native-user"}), reason="credit_finished")
    assert external.calls == []


def test_cisco_vpdn_termination_uses_source_session_identity():
    external = FakeExternalTerminationService(result=FakeLauncherResult(True))
    ras = make_ras("Cisco VPDN", attributes={"cisco_rsh_command": "/opt/ibs-addons/cisco/rsh_wrapper", "cisco_rsh_max_concurrent_connections": "5"})
    session = make_session("sid-1", {"User-Name": "native-user", "normal_username": "native-user", "Framed-IP-Address": "198.51.100.11"})
    SourceRASDisconnectClient(external_service=external).terminate(ras, session, "credit_finished")
    name, kwargs = external.calls[0]
    assert name == "cisco_vpdn" and kwargs["username"] == "native-user"
    assert kwargs["remote_ip"] == "198.51.100.11" and kwargs["max_concurrent_connections"] == 5


def test_cisco_vpdn_termination_fails_closed_without_source_username():
    external = FakeExternalTerminationService(result=FakeLauncherResult(True))
    with pytest.raises(PermanentRASTerminationError, match="source-defined username"):
        SourceRASDisconnectClient(external_service=external).terminate(make_ras("Cisco VPDN"), make_session(attrs={"Framed-IP-Address": "198.51.100.11"}), "credit_finished")
    assert external.calls == []
