"""br-r37-c1-ktwbg: empty_graph signature default parity."""

from __future__ import annotations

import inspect

import networkx as nx
import pytest

import franken_networkx as fnx


def test_empty_graph_default_signature_matches_networkx():
    fnx_view = str(inspect.signature(fnx.empty_graph))
    nx_view = str(inspect.signature(nx.empty_graph))

    if fnx_view != nx_view:
        pytest.fail(f"fnx {fnx_view} != nx {nx_view}")
    if not isinstance(fnx.empty_graph(), fnx.Graph):
        pytest.fail("fnx.empty_graph() should keep returning fnx.Graph")
