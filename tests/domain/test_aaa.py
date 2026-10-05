from atd_radius.domain.aaa import AAAAction, AAARequest, AAAResult, PluginPipeline

class AddAttrs:
    def __init__(self, attrs): self.attrs=attrs
    def evaluate(self, request): return AAAResult(AAAAction.ACCEPT, self.attrs)

class Reject:
    def evaluate(self, request): return AAAResult(AAAAction.REJECT, {"stage":"reject"}, "policy")

def test_pipeline_preserves_order_and_merges_attributes():
    result=PluginPipeline([AddAttrs({"group":"gold"}), AddAttrs({"timeout":"60"})]).evaluate(AAARequest("u"))
    assert result.action is AAAAction.ACCEPT
    assert result.attributes == {"group":"gold","timeout":"60"}

def test_first_terminal_decision_stops_pipeline():
    result=PluginPipeline([AddAttrs({"group":"gold"}), Reject(), AddAttrs({"never":"seen"})]).evaluate(AAARequest("u"))
    assert result.action is AAAAction.REJECT
    assert result.attributes == {"group":"gold","stage":"reject"}
    assert result.reason=="policy"
