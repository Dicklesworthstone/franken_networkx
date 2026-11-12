"""The network-text renderers must sit where networkx puts them.

br-r37-c1-s2nw9. networkx defines ``generate_network_text`` and
``write_network_text`` in ``networkx/readwrite/text.py`` and re-exports them at
TOP LEVEL only — ``nx.drawing.generate_network_text`` raises AttributeError.
fnx defines them in ``drawing/nx_pylab.py`` and used to surface them through
``drawing/__init__.py``, so ``fnx.drawing.<name>`` resolved where nx's does not.

Placement is asserted against live networkx on every module path rather than
hard-coded, so if upstream moves them this suite says so instead of silently
enshrining today's layout.
"""

from __future__ import annotations

import io

import networkx as nx
import pytest

import franken_networkx as fnx

_NAMES = ["generate_network_text", "write_network_text"]


@pytest.mark.parametrize("name", _NAMES)
def test_placement_matches_networkx_on_every_module_path(name):
    """Same answer as nx for `hasattr` on each namespace that could carry it."""
    for nx_module, fnx_module, label in (
        (nx, fnx, "top level"),
        (nx.drawing, fnx.drawing, "drawing"),
        (nx.readwrite, fnx.readwrite, "readwrite"),
    ):
        assert hasattr(fnx_module, name) == hasattr(nx_module, name), (
            f"{label}.{name}: fnx={hasattr(fnx_module, name)} "
            f"nx={hasattr(nx_module, name)}"
        )


@pytest.mark.parametrize("name", _NAMES)
def test_drawing_namespace_does_not_carry_it(name):
    """The specific divergence this bead was filed for, stated directly."""
    assert not hasattr(nx.drawing, name), "networkx changed; re-derive this test"
    assert not hasattr(fnx.drawing, name)


@pytest.mark.parametrize("name", _NAMES)
def test_top_level_still_carries_it(name):
    assert hasattr(nx, name), "networkx changed; re-derive this test"
    assert hasattr(fnx, name)
    assert callable(getattr(fnx, name))


def test_readwrite_forwarder_does_not_recurse():
    """`readwrite` forwards to the top-level name — the two must not be circular.

    `franken_networkx.readwrite.generate_network_text` calls
    `franken_networkx.generate_network_text`. Binding the top-level name FROM
    readwrite therefore recurses until the stack dies; this caught exactly that
    while the fix was being written. The top-level import must come from the
    defining module (`drawing.nx_pylab`) instead.
    """
    graph = fnx.path_graph(4)
    assert list(fnx.readwrite.generate_network_text(graph)) == list(
        nx.generate_network_text(nx.path_graph(4))
    )


_FIXTURES = [
    pytest.param(lambda m: m.path_graph(4), id="path"),
    pytest.param(lambda m: m.star_graph(5), id="star"),
    pytest.param(lambda m: m.balanced_tree(2, 3), id="tree"),
    pytest.param(lambda m: m.DiGraph([(0, 1), (1, 2), (0, 2)]), id="directed"),
    pytest.param(lambda m: m.MultiGraph([(0, 1), (0, 1), (1, 2)]), id="multi"),
    pytest.param(lambda m: m.Graph([(0, 1), (2, 3)]), id="disconnected"),
    pytest.param(lambda m: m.Graph(), id="empty"),
]

_OPTIONS = [
    pytest.param({}, id="default"),
    pytest.param({"with_labels": False}, id="no-labels"),
    pytest.param({"ascii_only": True}, id="ascii"),
    pytest.param({"vertical_chains": True}, id="vertical"),
    pytest.param({"max_depth": 2}, id="depth2"),
]


@pytest.mark.parametrize("build", _FIXTURES)
@pytest.mark.parametrize("options", _OPTIONS)
def test_generate_matches_networkx(build, options):
    """Moving the import must not change a single emitted line."""
    assert list(fnx.generate_network_text(build(fnx), **options)) == list(
        nx.generate_network_text(build(nx), **options)
    )


@pytest.mark.parametrize("build", _FIXTURES)
@pytest.mark.parametrize("options", _OPTIONS)
def test_write_matches_networkx(build, options):
    fnx_sink, nx_sink = io.StringIO(), io.StringIO()
    fnx.write_network_text(build(fnx), path=fnx_sink.write, **options)
    nx.write_network_text(build(nx), path=nx_sink.write, **options)
    assert fnx_sink.getvalue() == nx_sink.getvalue()


def test_drawing_star_export_surface_still_matches_networkx():
    """The surface br-r37-c1-ibcok fixed must not regress from this change.

    `nx.drawing` declares no `__all__`, so its star surface is its public
    `dir()` — the same comparison
    `test_drawing_package_star_export_surface_matches_networkx` makes. Removing
    the two renderers from `drawing/__init__.py` must leave that equality intact.
    """
    nx_surface = {n for n in dir(nx.drawing) if not n.startswith("_")}
    assert set(fnx.drawing.__all__) == nx_surface
    for name in _NAMES:
        assert name not in nx_surface
        assert name not in fnx.drawing.__all__
