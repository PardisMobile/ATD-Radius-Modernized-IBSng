"""RADIUS transport foundation.

The first implementation deliberately separates UDP transport from the AAA
application service. Attribute dictionaries and authentication methods are
added incrementally after parity tests against IBSng behavior.
"""

import asyncio

from atd_radius.protocols.radius import RadiusPacket


class RadiusDatagram(asyncio.DatagramProtocol):
    def __init__(self, on_packet):
        self.on_packet = on_packet

    def datagram_received(self, data: bytes, addr) -> None:
        try:
            packet = RadiusPacket.decode(data)
            self.on_packet(packet, addr)
        except ValueError:
            # Invalid datagrams are rejected at the transport boundary.
            return


async def serve(host: str, port: int, on_packet):
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: RadiusDatagram(on_packet), local_addr=(host, port)
    )
    return transport
