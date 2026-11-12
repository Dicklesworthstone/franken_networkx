"""Export-surface locks for br-r37-c1-dxqcf and br-r37-c1-e5ilz.

Both beads declared an ``__all__`` and both asked for "focused no-mock
packaging coverage" that never landed. The declarations are load-bearing in
two different ways, so they are pinned differently here:

* ``franken_networkx._network_simplex_native`` (br-r37-c1-e5ilz) is the
  private native port, and intentionally exposes ONE callable. Its module
  globals hold imported helpers — ``ceil``, ``chain``, ``islice``, ``sqrt``,
  ``repeat``, ``nx``, ``not_implemented_for`` — every one of which
  ``import *`` would leak if ``__all__`` were dropped. Note this is NOT
  ``franken_networkx.algorithms.flow.networksimplex``: that name resolves to
  networkx's own module object, so asserting anything about it against
  networkx would compare a module with itself and pass no matter what the port
  does. The port is compared against nx's module — two distinct objects that
  must agree on the single exported name.

* ``franken_networkx.backend`` (br-r37-c1-dxqcf) has no networkx counterpart
  (there is no ``networkx.backends`` module), so its contract is anchored to
  the thing that actually consumes it: the ``[project.entry-points]`` table in
  pyproject.toml. networkx resolves those ``module:attr`` strings at dispatch
  time, so a rename that keeps the code working in-tree still breaks the
  installed backend. The test reads the real pyproject and imports the real
  targets — no mocks, no copied literals.
"""

from __future__ import annotations

import importlib
import pathlib
import tomllib

import networkx as nx
import pytest

PORT = "franken_networkx._network_simplex_native"
NX_NETWORKSIMPLEX = "networkx.algorithms.flow.networksimplex"

# Names that live in the networksimplex module's globals purely because it
# imported them. None may escape through ``import *``.
LEAKABLE_HELPERS = ["ceil", "chain", "islice", "sqrt", "repeat", "nx", "not_implemented_for"]

PYPROJECT = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"


def _star_import_names(module_name):
    """The names a real ``from <module> import *`` would actually bind."""
    namespace = {}
    exec(f"from {module_name} import *", namespace)  # noqa: S102 - that IS the contract
    return {name for name in namespace if not name.startswith("__")}


def test_port_is_a_distinct_module_from_networkx():
    """Guard against the comparison silently becoming a module-vs-itself check."""
    port = importlib.import_module(PORT)
    nx_mod = importlib.import_module(NX_NETWORKSIMPLEX)
    assert port is not nx_mod
    assert pathlib.Path(port.__file__).name == "_network_simplex_native.py"


def test_port_all_matches_networkx_networksimplex():
    port = importlib.import_module(PORT)
    nx_mod = importlib.import_module(NX_NETWORKSIMPLEX)
    assert port.__all__ == nx_mod.__all__ == ["network_simplex"]


def test_port_star_import_leaks_no_helpers():
    """br-r37-c1-e5ilz: the reason the declaration exists at all."""
    assert _star_import_names(PORT) == {"network_simplex"}


@pytest.mark.parametrize("helper", LEAKABLE_HELPERS)
def test_port_helper_is_present_but_unexported(helper):
    """The helpers must really be there, or the leak test proves nothing."""
    port = importlib.import_module(PORT)
    assert hasattr(port, helper), f"{helper} is no longer imported; the leak test is now vacuous"
    assert helper not in port.__all__


def test_port_exported_name_resolves_and_is_callable():
    port = importlib.import_module(PORT)
    for name in port.__all__:
        assert callable(getattr(port, name))


def test_backend_module_all_is_declared_and_resolves():
    """br-r37-c1-dxqcf: every declared name exists and nothing extra escapes."""
    backend = importlib.import_module("franken_networkx.backend")
    assert isinstance(backend.__all__, list) and backend.__all__
    for name in backend.__all__:
        assert hasattr(backend, name), name
    assert _star_import_names("franken_networkx.backend") == set(backend.__all__)


def _declared_entry_points():
    with PYPROJECT.open("rb") as handle:
        table = tomllib.load(handle)["project"]["entry-points"]
    return [
        (group, name, target)
        for group, entries in table.items()
        for name, target in entries.items()
    ]


def test_pyproject_declares_the_networkx_backend_entry_points():
    groups = {group for group, _name, _target in _declared_entry_points()}
    assert {"networkx.backends", "networkx.backend_info"} <= groups


@pytest.mark.parametrize(
    ("group", "name", "target"),
    _declared_entry_points(),
    ids=lambda value: str(value).replace(".", "_"),
)
def test_declared_entry_point_target_actually_resolves(group, name, target):
    """networkx resolves these strings at dispatch time, so they must import.

    A rename inside the package that leaves in-tree callers working still
    breaks the INSTALLED backend, which is the failure this pins.
    """
    module_name, _, attribute = target.partition(":")
    module = importlib.import_module(module_name)
    assert attribute, f"{group}:{name} must name an attribute, got {target!r}"
    resolved = getattr(module, attribute)
    assert resolved is not None


def test_backend_entry_point_target_is_exported_by_the_backend_module():
    """The dispatch target must be part of the declared surface, not incidental."""
    backend = importlib.import_module("franken_networkx.backend")
    targets = {
        target.partition(":")[2]
        for group, _name, target in _declared_entry_points()
        if group == "networkx.backends" and target.startswith("franken_networkx.backend:")
    }
    assert targets, "no networkx.backends entry point points at franken_networkx.backend"
    assert targets <= set(backend.__all__)


def test_backend_info_entry_point_returns_the_shape_networkx_reads():
    """get_backend_info feeds nx's backend registry; it must stay a mapping."""
    module_name, _, attribute = next(
        target for group, _name, target in _declared_entry_points()
        if group == "networkx.backend_info"
    ).partition(":")
    info = getattr(importlib.import_module(module_name), attribute)()
    assert isinstance(info, dict)
    assert "functions" in info
    # nx reads this to decide what the backend claims to implement.
    assert isinstance(info["functions"], dict)


def test_networkx_is_the_live_library_not_a_stub():
    """No-mock guard: these assertions are only meaningful against real nx."""
    assert nx.__version__
    assert pathlib.Path(nx.__file__).exists()
