"""No fnx submodule may hand back networkx's object when fnx has a native one.

br-r37-c1-2qsqf. `from networkx.<x> import *` at the top of a submodule binds
networkx's function objects into that namespace. Where fnx also has a *different*
top-level implementation, `from franken_networkx.<ns> import fn` then silently
returns nx's version while `fnx.fn` returns the native one — same import, two
implementations, and nothing tells the user which they got.

This is object identity, not behaviour, so the check is exact and needs no
extension module. The bead was filed with ~185 shadowed names across 24
namespaces; all but `convert` had been repaired one namespace at a time without
a guard to keep them repaired. This is that guard.
"""

from __future__ import annotations

import importlib
import os
import pathlib
import subprocess
import sys

import pytest

import franken_networkx as fnx

# The 24 leaf namespaces the audit covers, plus the two recorded as fixed first.
NAMESPACES = [
    "operators", "components", "traversal", "connectivity", "tree", "dag",
    "flow", "clique", "readwrite", "convert", "chordal", "euler", "triads",
    "core", "classes", "regular", "relabel", "planarity", "smallworld",
    "bipartite", "distance_regular", "hybrid", "minors", "swap",
    "convert_matrix", "linalg",
]

_NX_CANDIDATES = (
    "networkx.algorithms.{}",
    "networkx.{}",
    "networkx.algorithms.operators.{}",
    "networkx.linalg.{}",
)


def _fresh_attribute_module(namespace):
    """What `fnx.<namespace>` resolves to in a FRESH interpreter.

    This must be a subprocess. `franken_networkx.<ns>` and
    `importlib.import_module("franken_networkx.<ns>")` are not the same object:
    the package's `__getattr__` falls through to `getattr(networkx, name)` for
    submodules outside its allowlist, so `fnx.<ns>` can BE networkx's module.
    Importing the real submodule for any reason then binds it onto the parent
    package and hides the whole problem — which is exactly what happened to the
    first version of this test, and why it passed against the unfixed tree.
    """
    probe = (
        "import networkx, franken_networkx as fnx;"
        f"print(getattr(getattr(fnx, {namespace!r}, None), '__name__', 'MISSING'))"
    )
    # Point the child at the SAME package tree this test imported. A bare
    # subprocess inherits PYTHONPATH but not the sys.path entry conftest injects,
    # so without this it silently probes whatever franken_networkx is installed
    # in site-packages and reports on a different tree than the one under test.
    package_parent = str(pathlib.Path(fnx.__file__).resolve().parent.parent)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [package_parent, env["PYTHONPATH"]] if env.get("PYTHONPATH") else [package_parent]
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-400:]
    resolved = result.stdout.strip().splitlines()[-1]
    return resolved


def _networkx_counterpart(namespace):
    for pattern in _NX_CANDIDATES:
        try:
            return importlib.import_module(pattern.format(namespace))
        except ImportError:
            continue
    return None


def _shadowed_names(namespace):
    """Names where the fnx namespace yields nx's object but fnx.<name> differs."""
    ours = importlib.import_module(f"franken_networkx.{namespace}")
    theirs = _networkx_counterpart(namespace)
    assert theirs is not None, f"no networkx counterpart for {namespace}"

    shadowed = []
    for name in dir(theirs):
        if name.startswith("_"):
            continue
        their_object = getattr(theirs, name, None)
        top_level = getattr(fnx, name, None)
        if their_object is None or top_level is None:
            continue
        if getattr(ours, name, None) is not their_object:
            continue  # routed
        if top_level is their_object:
            continue  # fnx deliberately re-exports nx's object; nothing to shadow
        if not callable(top_level) and not isinstance(top_level, type):
            continue
        shadowed.append(name)
    return sorted(shadowed)


@pytest.mark.parametrize("namespace", NAMESPACES)
def test_namespace_does_not_shadow_a_native(namespace):
    shadowed = _shadowed_names(namespace)
    assert shadowed == [], (
        f"franken_networkx.{namespace} returns networkx's object for {shadowed}, "
        f"but franken_networkx.<name> is a different (native) implementation"
    )


@pytest.mark.parametrize("namespace", NAMESPACES)
def test_attribute_path_is_not_networkxs_module(namespace):
    """`fnx.<ns>` must be fnx's submodule, not networkx's module of that name.

    Distinct from the test above: that one asks whether the fnx submodule routes
    its names, this one asks whether you reach the fnx submodule AT ALL through
    attribute access. `convert` failed only this one — its file routed correctly
    while `fnx.convert` was `networkx.convert`.
    """
    resolved = _fresh_attribute_module(namespace)
    assert not resolved.startswith("networkx"), (
        f"fnx.{namespace} resolves to {resolved} in a fresh interpreter, so every "
        f"name reached through it is networkx's, whatever the fnx submodule says"
    )


@pytest.mark.parametrize(
    "name",
    [
        "from_dict_of_dicts",
        "from_dict_of_lists",
        "from_edgelist",
        "to_edgelist",
        "to_networkx_graph",
    ],
)
def test_convert_namespace_routes_to_the_native(name):
    """The five names br-r37-c1-2qsqf still listed as shadowed on 2026-08-05."""
    import networkx.convert as nx_convert

    from franken_networkx import convert as fnx_convert

    routed = getattr(fnx_convert, name)
    assert routed is not getattr(nx_convert, name)
    assert routed.__doc__ is not None
    assert f"franken_networkx.{name}" in routed.__doc__


def test_convert_namespace_values_match_networkx():
    """Routing changed which implementation runs; it must not change results."""
    import networkx as nx
    import networkx.convert as nx_convert

    from franken_networkx import convert as fnx_convert

    edges = [(0, 1), (1, 2), (2, 0)]
    nx_graph = nx.Graph(edges)
    dict_of_dicts = nx.to_dict_of_dicts(nx_graph)
    dict_of_lists = nx.to_dict_of_lists(nx_graph)

    builders = [
        ("from_dict_of_dicts", dict_of_dicts),
        ("from_dict_of_lists", dict_of_lists),
        ("from_edgelist", edges),
        ("to_networkx_graph", dict_of_dicts),
    ]
    for name, payload in builders:
        expected = getattr(nx_convert, name)(payload)
        actual = getattr(fnx_convert, name)(payload)
        # fnx types on the fnx path — that is the point of routing — same content.
        assert isinstance(actual, fnx.Graph), f"{name} did not return an fnx graph"
        assert sorted(actual.nodes()) == sorted(expected.nodes()), name
        assert sorted(map(sorted, actual.edges())) == sorted(
            map(sorted, expected.edges())
        ), name

    fnx_graph = fnx.Graph(edges)
    assert sorted(map(str, fnx_convert.to_edgelist(fnx_graph))) == sorted(
        map(str, nx_convert.to_edgelist(nx_graph))
    )


def test_convert_router_forwards_keywords():
    """`create_using` and friends must survive the hop, not be swallowed."""
    from franken_networkx import convert as fnx_convert

    edges = [(0, 1), (1, 2)]
    directed = fnx_convert.from_edgelist(edges, create_using=fnx.DiGraph)
    assert directed.is_directed()
    assert sorted(directed.edges()) == [(0, 1), (1, 2)]

    multi = fnx_convert.from_dict_of_dicts(
        {0: {1: {0: {}}}, 1: {0: {0: {}}}},
        create_using=fnx.MultiGraph,
        multigraph_input=True,
    )
    assert multi.is_multigraph()
