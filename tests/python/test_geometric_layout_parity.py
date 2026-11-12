"""Differential parity for deterministic geometric layout functions.

``test_layout_parity.py`` covers the force-directed spring layout; this
adds the deterministic geometric layouts ``circular_layout``,
``shell_layout``, ``spiral_layout``, ``random_layout`` (seeded) and
``spectral_layout``. None of these had dedicated coverage. Layouts return
``node -> position`` dicts of numpy arrays.

``spectral_layout`` is compared up to sign (eigenvector sign is
arbitrary); the others byte-for-byte against networkx.

br-r37-c1-qwj6b
"""

from __future__ import annotations

import random

import numpy as np
import pytest
import networkx as nx
import franken_networkx as fnx


def _pair(seed, p=0.4):
    rng = random.Random(seed)
    n = rng.randint(4, 9)
    fg = fnx.Graph()
    ng = nx.Graph()
    fg.add_nodes_from(range(n))
    ng.add_nodes_from(range(n))
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                fg.add_edge(u, v)
                ng.add_edge(u, v)
    return fg, ng


def _assert_positions_close(fp, np_, abs_tol=1e-7, by_abs=False):
    assert set(fp) == set(np_)
    for k in np_:
        a = np.asarray(fp[k], dtype=float)
        b = np.asarray(np_[k], dtype=float)
        if by_abs:
            a, b = np.abs(a), np.abs(b)
        assert np.allclose(a, b, atol=abs_tol)


@pytest.mark.parametrize("fn", ["circular_layout", "shell_layout", "spiral_layout"])
@pytest.mark.parametrize("seed", range(25))
def test_deterministic_layout_matches_networkx(fn, seed):
    fg, ng = _pair(seed)
    _assert_positions_close(getattr(fnx, fn)(fg), getattr(nx, fn)(ng))


@pytest.mark.parametrize("seed", range(25))
def test_random_layout_seeded_matches_networkx(seed):
    fg, ng = _pair(seed)
    _assert_positions_close(fnx.random_layout(fg, seed=7), nx.random_layout(ng, seed=7))


@pytest.mark.parametrize("seed", range(25))
def test_spectral_layout_matches_networkx_up_to_sign(seed):
    fg, ng = _pair(seed)
    _assert_positions_close(
        fnx.spectral_layout(fg), nx.spectral_layout(ng), abs_tol=1e-5, by_abs=True
    )


def test_circular_layout_goldens():
    fp = fnx.circular_layout(fnx.cycle_graph(6))
    # Circular layout is 2D and centred at the origin.
    assert all(len(v) == 2 for v in fp.values())
    assert np.allclose(np.mean(list(fp.values()), axis=0), 0, atol=1e-9)
    assert all(
        np.allclose(fp[k], nx.circular_layout(nx.cycle_graph(6))[k]) for k in fp
    )
