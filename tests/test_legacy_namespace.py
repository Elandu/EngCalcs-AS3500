from importlib import import_module
from importlib.metadata import entry_points


def test_previous_package_module_is_an_alias() -> None:
    assert import_module("opencalcs_as3500.plugin") is import_module("engcalcs_as3500.plugin")


def test_previous_entry_point_group_still_loads() -> None:
    matches = [item for item in entry_points(group="opencalcs.plugins") if item.name == "as3500"]
    assert len(matches) == 1
    assert matches[0].load()() is not None
