"""Parity for nested ``franken_networkx.algorithms.connectivity`` imports."""

from __future__ import annotations

import importlib


def test_algorithms_connectivity_cuts_submodule_imports_like_networkx():
    actual = importlib.import_module(
        "franken_networkx.algorithms.connectivity.cuts"
    )
    expected = importlib.import_module("networkx.algorithms.connectivity.cuts")

    assert actual is expected


def test_algorithms_connectivity_from_import_exposes_cuts_module():
    from franken_networkx.algorithms.connectivity import cuts

    expected = importlib.import_module("networkx.algorithms.connectivity.cuts")

    assert cuts.minimum_st_edge_cut is expected.minimum_st_edge_cut
