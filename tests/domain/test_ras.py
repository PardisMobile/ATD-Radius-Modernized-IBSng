from atd_radius.domain.ras import RAS, RASPort

def test_ras_attribute_precedence_matches_a124():
    ras = RAS(10, "10.0.0.1", "edge", "mikrotik", "secret",
              attributes={"online_check": "0", "x": "user"},
              type_defaults={"online_check": 1, "x": "type"})
    assert ras.get_attribute("online_check") == "0"
    assert ras.get_attribute("x") == "user"

def test_ras_default_attribute_is_available_without_persistence():
    ras = RAS(1, "10.0.0.1", "edge", "generic", "secret")
    assert ras.get_attribute("online_check") == 1
    assert ras.should_check_online()

def test_ras_ports_and_ip_pools_are_explicit_runtime_state():
    ras = RAS(1, "10.0.0.1", "edge", "generic", "secret",
              ports={"ppp0": RASPort("ppp0", type="Internet")}, ippool_ids=(3, 4))
    assert ras.has_port("ppp0")
    assert ras.has_ippool(4)
