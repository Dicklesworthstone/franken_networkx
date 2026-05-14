"""br-r37-c1-u3umv: regression — nx.X_layout(fnx_graph) matches
nx.X_layout(nx_graph) for the same seed / inputs.

Before this fix, ``nx.drawing.layout._process_params`` performed
``isinstance(G, nx.Graph)`` and, when False, discarded the input and
rebuilt a *node-only* nx.Graph via ``empty.add_nodes_from(G)``.
fnx graph classes are not nx.Graph subclasses, so every layout
helper that funnels through ``_process_params`` (spring/fr/spectral/
kk/planar/random/shell/...) silently ran on an edge-less graph and
returned positions that ignored connectivity.

fnx now monkey-patches ``_process_params`` at import time to convert
fnx graphs to nx graphs (with edges) before invoking the original
helper. This file locks in that fix.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx

try:
    import networkx as nx
    import numpy as np

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


needs_deps = pytest.mark.skipif(not HAS_DEPS, reason="networkx/numpy not installed")


@needs_deps
@pytest.mark.parametrize(
    "fname,seeded",
    [
        ("spring_layout", True),
        ("fruchterman_reingold_layout", True),
        ("random_layout", True),
        ("spectral_layout", False),
        ("kamada_kawai_layout", False),
        ("circular_layout", False),
    ],
)
def test_nx_layout_with_fnx_graph_matches_nx(fname, seeded):
    """nx.X_layout(fnx_graph) returns the same positions as
    nx.X_layout(nx_graph) for an isomorphic graph + same kwargs."""
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    kwargs = {"seed": 42} if seeded else {}
    f_fn = getattr(nx, fname)
    pf = f_fn(fg, **kwargs)
    pn = f_fn(ng, **kwargs)
    assert set(pf) == set(pn)
    for key in pf:
        assert np.allclose(pf[key], pn[key]), (
            f"{fname}: pf[{key}]={pf[key]} != pn[{key}]={pn[key]}"
        )


@needs_deps
def test_nx_shell_layout_with_fnx_graph_matches_nx():
    fg = fnx.complete_graph(6)
    ng = nx.complete_graph(6)
    pf = nx.shell_layout(fg, nlist=[[0, 1, 2], [3, 4, 5]])
    pn = nx.shell_layout(ng, nlist=[[0, 1, 2], [3, 4, 5]])
    for key in pf:
        assert np.allclose(pf[key], pn[key])


@needs_deps
def test_process_params_preserves_edges_for_fnx_graphs():
    """Direct check that the patched ``_process_params`` no longer
    strips edges from fnx graphs."""
    import networkx.drawing.layout as _layout

    fg = fnx.path_graph(5)
    fg[2][3]["weight"] = 99
    processed, _ = _layout._process_params(fg, None, 2)
    assert processed.number_of_edges() == 4
    assert processed[2][3]["weight"] == 99


@needs_deps
def test_spring_layout_positions_reflect_edges_for_fnx_graph():
    """Before the fix, the positions were essentially random scatter
    (no edge information used). After the fix, neighbouring nodes on
    a path should end up roughly adjacent in the layout."""
    fg = fnx.path_graph(10)
    pos = nx.spring_layout(fg, seed=42)
    # Adjacent-pair distance should be smaller than far-pair distance.
    adj_dist = np.linalg.norm(pos[0] - pos[1])
    far_dist = np.linalg.norm(pos[0] - pos[9])
    assert adj_dist < far_dist
