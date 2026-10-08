"""ChilliSpot disconnect operation wired to the authenticated RADIUS UDP client."""
from __future__ import annotations

from atd_radius.domain.radius import RadiusPacket
from atd_radius.domain.ras_external import (\n    build_chillispot_disconnect_packet,\n    build_chillispot_disconnect_request,\n)
from atd_radius.infrastructure.radius_control_udp import RadiusControlUDPClient


class ChilliSpotDisconnectClient:
    """Execute the source-traced ChilliSpot Disconnect-Request operation."""

    def __init__(self, control_client: RadiusControlUDPClient | None = None) -> None:
        self.control_client = control_client or RadiusControlUDPClient()

    def disconnect(
        self,
        *,
        disconnect_ip: str,
        disconnect_port: int,
        username: str,
        identifier: int,
        secret: str,
    ) -> RadiusPacket:
        build_chillispot_disconnect_request(
            disconnect_ip=disconnect_ip,
            disconnect_port=disconnect_port,
            username=username,
        )
        packet = build_chillispot_disconnect_packet(
            username=username,
            identifier=identifier,
        )
        return self.control_client.send(
            (disconnect_ip, disconnect_port),
            packet,
            secret,
        )
