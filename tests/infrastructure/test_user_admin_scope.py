from atd_radius.infrastructure import UserRepository


class Result:
    def __init__(self, one=None, many=()):
        self.one = one
        self.many = list(many)

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class Conn:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self.results.pop(0)


def test_create_persists_authenticated_owner_and_selected_group():
    conn = Conn([Result((42,)), Result(), Result()])
    record = UserRepository(conn).create("alice", owner_id=7, group_id=9)
    assert record.id == 42
    assert record.owner_id == 7
    assert record.group_id == 9
    assert "owner_id, group_id" in conn.calls[1][0]
    assert conn.calls[1][1] == (42, 0, 7, 9)


def test_user_list_and_count_can_be_scoped_to_native_owner():
    conn = Conn([
        Result(many=[(42, "alice", False, 7, 9)]),
        Result((1,)),
    ])
    repo = UserRepository(conn)
    records = repo.list(owner_id=7)
    total = repo.count(owner_id=7)
    assert records[0].owner_id == 7
    assert records[0].group_id == 9
    assert total == 1
    assert "u.owner_id = %s" in conn.calls[0][0]
    assert conn.calls[0][1] == [7, 50, 0]
    assert "u.owner_id = %s" in conn.calls[1][0]
    assert conn.calls[1][1] == [7]


def test_user_lookup_returns_owner_and_group_for_authorization():
    conn = Conn([Result((42, "alice", False, 7, 9))])
    record = UserRepository(conn).get_by_username("alice")
    assert record is not None
    assert record.owner_id == 7
    assert record.group_id == 9
