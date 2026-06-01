from fan_kg.utils import normalize_name, parse_list, stable_id


def test_normalize_name_removes_common_company_suffixes():
    assert normalize_name("美的集团股份有限公司") == "美的集团"


def test_parse_list_accepts_delimited_text():
    assert parse_list("a;b;c") == ["a", "b", "c"]


def test_stable_id_is_stable():
    assert stable_id("fan", "2025-07") == stable_id("fan", "2025-07")
