from __future__ import annotations

import pytest

from atd_radius.domain.ras_external import build_asterisk_manager_hangup_request
from atd_radius.infrastructure.asterisk_manager_transport import AsteriskManagerTransport, AsteriskManagerTransportError


class FakeSocket:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.sent = []
        self.timeout = None
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def settimeout(self, timeout): self.timeout = timeout
    def sendall(self, payload): self.sent.append(payload)
    def recv(self, _size): return self.chunks.pop(0) if self.chunks else b""


def _request():
    return build_asterisk_manager_hangup_request(
        ras_ip="192.0.2.9", manager_port="5038", username="admin",
        secret="manager-secret", timeout="7", channel="PJSIP/alice-000001",
    )


def test_ami_transport_authenticates_then_hangs_up_exact_source_channel():
    holder = {}
    response = (
        b"Asterisk Call Manager/1.1\r\n"
        b"Response: Success\r\nActionID: 1\r\nMessage: Authentication accepted\r\n\r\n"
        b"Response: Success\r\nActionID: 2\r\nMessage: Channel Hungup\r\n\r\n"
    )
    def factory(address, timeout):
        holder["address"] = address
        holder["factory_timeout"] = timeout
        holder["socket"] = FakeSocket([response])
        return holder["socket"]
    result = AsteriskManagerTransport(socket_factory=factory).execute(_request())
    assert result.succeeded is True
    assert result.login_message == "Authentication accepted"
    assert result.hangup_message == "Channel Hungup"
    assert holder["address"] == ("192.0.2.9", 5038)
    assert holder["factory_timeout"] == 7.0
    assert holder["socket"].timeout == 7.0
    assert holder["socket"].sent == [
        b"Username: admin\r\nSecret: manager-secret\r\nAction: Login\r\nActionID: 1\r\n\r\n",
        b"channel: PJSIP/alice-000001\r\nAction: Hangup\r\nActionID: 2\r\n\r\n",
    ]


def test_ami_transport_rejects_manager_login_failure_without_hangup():
    fake = FakeSocket([b"Response: Error\r\nActionID: 1\r\nMessage: Authentication failed\r\n\r\n"])
    with pytest.raises(AsteriskManagerTransportError, match="Authentication failed"):
        AsteriskManagerTransport(socket_factory=lambda *_a, **_k: fake).execute(_request())
    assert len(fake.sent) == 1


def test_ami_transport_skips_unrelated_event_and_matches_action_id():
    fake = FakeSocket([
        b"Event: FullyBooted\r\nPrivilege: system,all\r\n\r\n"
        b"Response: Success\r\nActionID: 1\r\nMessage: accepted\r\n\r\n"
        b"Response: Success\r\nActionID: 2\r\nMessage: hungup\r\n\r\n"
    ])
    result = AsteriskManagerTransport(socket_factory=lambda *_a, **_k: fake).execute(_request())
    assert result.login_message == "accepted"
    assert result.hangup_message == "hungup"


def test_ami_transport_rejects_wrong_operation_family():
    from atd_radius.domain.ras_external import ExternalOperation, ProviderOperationRequest
    request = ProviderOperationRequest("asterisk", ExternalOperation.H323, "disconnect", {})
    with pytest.raises(ValueError, match="only Asterisk Manager"):
        AsteriskManagerTransport().execute(request)
