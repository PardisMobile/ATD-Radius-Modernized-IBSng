from pathlib import Path

UI_FILES = [
    Path("ui/public/index.php"),
    Path("ui/public/users.php"),
    Path("ui/public/user.php"),
]

FORBIDDEN_OPERATOR_TERMS = (
    "Dashboard",
    "Users workspace",
    "User workspace",
    "Groups workspace",
    "Services workspace",
    "RAS / NAS",
    "IP Pools",
    "Sessions workspace",
    "Accounting workspace",
    "Billing workspace",
    "Administration",
    "System settings",
)

def test_ui_uses_ibsng_top_level_terminology():
    index = Path("ui/public/index.php").read_text(encoding="utf-8")
    for label in ("HOME", "USER", "GROUP", "REPORT", "GRAPH", "ADMIN", "SETTING"):
        assert label in index
    for term in FORBIDDEN_OPERATOR_TERMS:
        assert term not in index

def test_user_pages_do_not_reintroduce_atd_operator_taxonomy():
    for path in UI_FILES:
        text = path.read_text(encoding="utf-8")
        for term in FORBIDDEN_OPERATOR_TERMS:
            assert term not in text, f"{term!r} found in {path}"

def test_user_information_keeps_a124_names():
    text = Path("ui/public/user.php").read_text(encoding="utf-8")
    for label in ("User Information", "Group List", "RAS", "Connection Logs", "Credit Changes"):
        assert label in text

def test_user_list_keeps_a124_search_names():
    text = Path("ui/public/users.php").read_text(encoding="utf-8")
    for label in ("User Information", "Search User", "Add New User"):
        assert label in text
