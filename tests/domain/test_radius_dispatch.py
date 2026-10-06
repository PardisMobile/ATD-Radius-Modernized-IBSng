from atd_radius.domain.aaa import AAAAction,AAAResult,PluginPipeline
from atd_radius.domain.radius import RadiusCode,RadiusPacket
from atd_radius.domain.radius_dispatch import RadiusDispatcher

class Accept:
    def evaluate(self,request): return AAAResult(AAAAction.ACCEPT,{"Reply":"ok"})
class Reject:
    def evaluate(self,request): return AAAResult(AAAAction.REJECT,reason="bad")
class Control:
    def disconnect(self,attributes): return True
    def change_of_authorization(self,attributes): return True

def test_access_dispatches_pipeline():
    r=RadiusDispatcher(PluginPipeline([Accept()])).access(RadiusPacket(RadiusCode.ACCESS_REQUEST,9,{"User-Name":"alice"},b"x"))
    assert r.code is RadiusCode.ACCESS_ACCEPT and r.identifier==9 and r.attributes["Reply"]=="ok"

def test_reject_dispatches_access_reject():
    r=RadiusDispatcher(PluginPipeline([Reject()])).access(RadiusPacket(RadiusCode.ACCESS_REQUEST,1,{"User-Name":"x"}))
    assert r.code is RadiusCode.ACCESS_REJECT

def test_accounting_returns_event_and_response():
    r=RadiusDispatcher(PluginPipeline([])).accounting(RadiusPacket(RadiusCode.ACCOUNTING_REQUEST,4,{"User-Name":"u","Acct-Status-Type":"Start","Acct-Session-Id":"s"}))
    assert r.response.code is RadiusCode.ACCOUNTING_RESPONSE and r.accounting.session_id=="s"

def test_disconnect_and_coa_dispatch():
    p=RadiusDispatcher(PluginPipeline([]),Control())
    assert p.control(RadiusPacket(RadiusCode.DISCONNECT_REQUEST, 1, {"Acct-Session-Id":"s"})).code is RadiusCode.DISCONNECT_ACK
    assert p.control(RadiusPacket(RadiusCode.COA_REQUEST, 2, {"Acct-Session-Id":"s"})).code is RadiusCode.COA_ACK


class Context:
    def enrich(self, packet, source_ip=None):
        return {"User-Name": "enriched", "NAS-Identifier": "ras-1"}


def test_access_context_enriches_request_before_plugins():
    r = RadiusDispatcher(PluginPipeline([Accept()]), access_context=Context()).access(
        RadiusPacket(RadiusCode.ACCESS_REQUEST, 2, {"User-Name": "original"})
    )
    assert r.code is RadiusCode.ACCESS_ACCEPT
