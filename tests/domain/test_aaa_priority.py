from atd_radius.domain.aaa import AAAAction,AAARequest,AAAResult,PluginPipeline,PluginSpec

class Marker:
    def __init__(self,key): self.key=key
    def evaluate(self,request): return AAAResult(AAAAction.ACCEPT,{self.key:"1"})

def test_lower_numeric_priority_runs_first():
    p=PluginPipeline([PluginSpec(9,"late",Marker("late")),PluginSpec(1,"early",Marker("early"))])
    assert [x.name for x in p.plugins]==["early","late"]
    assert list(p.evaluate(AAARequest("u")).attributes)==["early","late"]
