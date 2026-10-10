from __future__ import annotations

import threading

import uvicorn

from atd_radius.api.app import app
from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, PostgresRadiusSecretResolver, NativeRadiusRuntimeState
from atd_radius.config import settings
from atd_radius.infrastructure.db import connection
from atd_radius.infrastructure.radius_udp import RadiusUDPServer


def _run_radius_server(server: RadiusUDPServer) -> None:
    while True:
        try:
            server.serve_once()
        except OSError:
            return


def _start_radius_servers() -> list[RadiusUDPServer]:
    state = NativeRadiusRuntimeState()
    # API and UDP packet handlers must share this exact in-process session owner.
    app.state.radius_runtime_state = state
    handler = NativeRadiusPacketHandler(state, connection)
    secrets = PostgresRadiusSecretResolver(connection)
    servers = [
        RadiusUDPServer(handler, secrets, settings.radius_auth_host, settings.radius_auth_port),
        RadiusUDPServer(handler, secrets, settings.radius_acct_host, settings.radius_acct_port),
    ]
    for server in servers:
        threading.Thread(target=_run_radius_server, args=(server,), daemon=True).start()
    return servers


if __name__ == "__main__":
    radius_servers = _start_radius_servers() if settings.radius_enabled else []
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        for server in radius_servers:
            server.close()
