from atd_radius.domain.radius_runtime import DuplicateRequestCache,RequestKey,SessionKey,SessionRegistry

def test_duplicate_key_matches_a124_source_ip_port_id_code():
    c=DuplicateRequestCache()
    k=RequestKey("10.0.0.1",1812,7,1)
    first=c.add(k)
    assert c.get(k) is first
    assert len(c)==1
    c.finish(k,"reply")
    assert c.get(k).finished and c.get(k).response=="reply"

def test_same_id_from_different_source_port_is_not_duplicate():
    c=DuplicateRequestCache()
    c.add(RequestKey("10.0.0.1",1812,7,1))
    assert c.get(RequestKey("10.0.0.1",1813,7,1)) is None


def test_session_registry_tracks_deltas_and_active_sessions():
    r=SessionRegistry(); k=SessionKey(4,2,"abc")
    r.start(k,{"User-Name":"u"})
    assert r.update(k,100,200)==(100,200)
    assert r.update(k,130,260)==(30,60)
    assert len(r.active_for_user(4))==1
    r.stop(k,140,280)
    assert not r.active_for_user(4)


def test_duplicate_cache_purges_old_entries():
    c = DuplicateRequestCache()
    k = RequestKey("10.0.0.1", 1812, 7, 1)
    item = c.add(k)
    assert c.purge_expired(10, now=item.created_at + 11) == 1
    assert c.get(k) is None

def test_session_registry_finds_session_by_acct_session_id():
    r = SessionRegistry()
    r.start(SessionKey(4, 2, "abc"))
    assert r.find_by_unique_id("abc") is not None
    assert r.find_by_unique_id("missing") is None
