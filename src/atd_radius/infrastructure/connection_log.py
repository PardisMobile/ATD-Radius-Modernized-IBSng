"""Persistence contract for the native A1.24 connection-log shape."""
from __future__ import annotations
from dataclasses import dataclass,field
from datetime import datetime
from typing import Protocol

@dataclass(frozen=True,slots=True)
class ConnectionLog:
    connection_log_id:int
    user_id:int|None
    credit_used:str|None
    login_time:datetime|None
    logout_time:datetime|None
    successful:bool
    service:int
    ras_id:int|None
    details:dict[str,str]=field(default_factory=dict)

class ConnectionLogRepository(Protocol):
    def create(self, record:ConnectionLog)->int: ...
    def add_detail(self, connection_log_id:int, name:str, value:str)->None: ...
    def close(self, connection_log_id:int, logout_time:datetime, credit_used:str|None=None, successful:bool|None=None)->None: ...
    def get(self, connection_log_id:int)->ConnectionLog|None: ...
