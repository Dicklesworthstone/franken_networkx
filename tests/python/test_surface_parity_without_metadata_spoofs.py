"""Surface parity must be implemented, not declared through metadata.

br-r37-c1-rc0923-epic-honest-measurement-vbneu.1: commit 07924ecdd reached
"4,129/4,129" by assigning ``__signature__`` to the four graph classes and
rewriting a look-alike ``EdgePartition`` enum's ``__module__``, while the
behaviour behind those rows still differed (invalid ``backend=`` accepted,
positional ``multigraph_input`` rejected, ``EdgePartition`` unpicklable). It
also swapped the package module classes, slowing every ``fnx.<attr>`` lookup
~4x. This file pins the real behaviour and the classifier checks that now
reject those spoofs.
"""

from __future__ import annotations

import enum
import importlib.util
import inspect
import pickle
import sys
from pathlib import Path

import networkx as nx
import pytest

import franken_networkx as fnx
import franken_networkx.algorithms as fnx_algorithms

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _coverage_matrix():
    path = Path(__file__).resolve().parents[2] / "scripts" / "generate_coverage_matrix.py"
    spec = importlib.util.spec_from_file_location("_fnx_coverage_matrix_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the classifier cannot be satisfied by metadata -------------------------


def test_classifier_flags_declared_class_signature():
    cm = _coverage_matrix()

    class Spoofed:
        def __init__(self, data=None):
            self.data = data

    Spoofed.__signature__ = inspect.signature(nx.Graph)
    assert cm._declared_class_signature_spoof(Spoofed)
    for name in CLASSES:
        assert not cm._declared_class_signature_spoof(getattr(fnx, name))


def test_classifier_flags_type_claiming_a_networkx_module_it_is_not_in():
    cm = _coverage_matrix()

    class LookAlike(enum.Enum):
        OPEN = 0
        INCLUDED = 1
        EXCLUDED = 2

    LookAlike.__module__ = "networkx.algorithms.tree.mst"
    LookAlike.__qualname__ = "EdgePartition"
    assert cm._type_module_spoof(LookAlike)
    assert not cm._type_module_spoof(nx.EdgePartition)
    assert not cm._type_module_spoof(type(fnx.EdgePartition.OPEN))
    assert not cm._type_module_spoof(int)


# --- graph constructors: networkx's real call shape ------------------------


@pytest.mark.parametrize("name", CLASSES)
def test_constructor_signature_is_real_and_matches_networkx(name):
    cls = getattr(fnx, name)
    assert "__signature__" not in vars(cls)
    assert str(inspect.signature(cls)) == str(inspect.signature(getattr(nx, name)))


@pytest.mark.parametrize("name", CLASSES)
def test_constructor_backend_validation_matches_networkx(name):
    with pytest.raises(ImportError, match="'no_such_backend' backend is not installed"):
        getattr(nx, name)(backend="no_such_backend")
    with pytest.raises(ImportError, match="'no_such_backend' backend is not installed"):
        getattr(fnx, name)(backend="no_such_backend")
    for ok in (None, "networkx", "franken_networkx"):
        G = getattr(fnx, name)([(0, 1)], backend=ok)
        assert list(G.edges()) == [(0, 1)]
        assert "backend" not in G.graph


@pytest.mark.parametrize("name", ["MultiGraph", "MultiDiGraph"])
def test_multigraph_input_positional_and_keyword_like_networkx(name):
    data = {0: {1: {0: {"w": 1}, 1: {"w": 2}}}}
    for args, kwargs in (((data, True), {}), ((data,), {"multigraph_input": True})):
        ref = getattr(nx, name)(*args, **kwargs)
        got = getattr(fnx, name)(*args, **kwargs)
        assert sorted(got.edges(keys=True, data=True)) == sorted(ref.edges(keys=True, data=True))
        assert dict(got.graph) == dict(ref.graph) == {}


@pytest.mark.parametrize("name", ["Graph", "DiGraph"])
def test_simple_graph_multigraph_input_is_a_graph_attribute_like_networkx(name):
    ref = getattr(nx, name)([(0, 1)], multigraph_input=True)
    got = getattr(fnx, name)([(0, 1)], multigraph_input=True)
    assert dict(got.graph) == dict(ref.graph) == {"multigraph_input": True}


@pytest.mark.parametrize("name", CLASSES)
def test_constructor_rejects_extra_positionals_like_networkx(name):
    extra = ([(0, 1)], True, "x") if name.startswith("Multi") else ([(0, 1)], True)
    with pytest.raises(TypeError):
        getattr(nx, name)(*extra)
    with pytest.raises(TypeError):
        getattr(fnx, name)(*extra)


# --- EdgePartition is networkx's enum --------------------------------------


def test_edge_partition_is_networkx_enum_and_pickles():
    assert fnx.EdgePartition is nx.EdgePartition
    for member in fnx.EdgePartition:
        assert pickle.loads(pickle.dumps(member)) is member


def test_partition_spanning_tree_honours_edge_partition():
    G = fnx.cycle_graph(4)
    for u, v in G.edges():
        G[u][v]["weight"] = 1
    G[0][1]["partition"] = fnx.EdgePartition.EXCLUDED
    G[2][3]["partition"] = fnx.EdgePartition.INCLUDED
    T = fnx.partition_spanning_tree(G)
    assert not T.has_edge(0, 1)
    assert T.has_edge(2, 3)


# --- namespace shape: functions like networkx, plain module classes ---------


@pytest.mark.parametrize("name", ["bridges", "reciprocity"])
def test_colliding_names_are_functions_like_networkx(name):
    assert inspect.isfunction(getattr(fnx, name)) == inspect.isfunction(getattr(nx, name))
    assert inspect.isfunction(getattr(fnx_algorithms, name))
    assert sys.modules[f"franken_networkx.{name}"].__name__ == f"franken_networkx.{name}"


def test_package_modules_use_plain_module_class():
    assert type(sys.modules["franken_networkx"]) is type(sys)
    assert type(fnx_algorithms) is type(sys)
