from atd_radius.domain.aaa import AAAAction, AAAResult, PluginPipeline, PluginSpec

class Policy:
    def __init__(self, value):
        self.value = value
    def evaluate(self, request):
        return AAAResult(AAAAction.ACCEPT, {self.value: self.value})

def test_equal_priority_preserves_registration_order():
    pipeline = PluginPipeline([
        PluginSpec(5, "z", Policy("first")),
        PluginSpec(5, "a", Policy("second")),
    ])
    assert [p.name for p in pipeline.plugins] == ["z", "a"]

def test_lower_priority_runs_first():
    pipeline = PluginPipeline([
        PluginSpec(7, "late", Policy("late")),
        PluginSpec(2, "early", Policy("early")),
    ])
    assert [p.name for p in pipeline.plugins] == ["early", "late"]
