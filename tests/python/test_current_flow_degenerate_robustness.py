"""fnx returns correct values for degenerate current-flow / katz inputs.

On graphs with fewer than 3 nodes, networkx CRASHES with an unhandled
``ZeroDivisionError`` (current_flow_betweenness/closeness — its n<3
normalization divides by zero) or ``TypeError`` (katz_centrality_numpy on a
single node). Those crashes are networkx's own unhandled edge cases, NOT a
documented contract (nx only deliberately raises ``NetworkXError("Graph not
connected")``).

fnx intentionally returns the mathematically-correct trivial value instead —
a single node has current-flow betweenness 0, two connected nodes have no node
lying between others, etc. This is a deliberate fnx-is-more-robust divergence
(br-r37-c1-bp6wk decision); the test pins fnx's correct behavior AND documents
that nx crashes here so the divergence is intentional, not accidental.

No mocks: real fnx (and a recorded note of nx's crash) on degenerate graphs.
"""

from __future__ import annotations

import pytest
import networkx as nx
import franken_networkx as fnx


def test_current_flow_betweenness_single_and_two_node():
    assert fnx.current_flow_betweenness_centrality(fnx.empty_graph(1)) == {0: 0.0}
    two = fnx.current_flow_betweenness_centrality(fnx.path_graph(2))
    assert two == {0: 0.0, 1: 0.0}
    # networkx crashes on the same input (its own unhandled n<3 edge case).
    with pytest.raises(ZeroDivisionError):
        nx.current_flow_betweenness_centrality(nx.path_graph(2))


def test_current_flow_closeness_two_node():
    vals = fnx.current_flow_closeness_centrality(fnx.path_graph(2))
    assert set(vals) == {0, 1}
    assert all(v == pytest.approx(1.0) for v in vals.values())


def test_katz_numpy_single_node():
    assert fnx.katz_centrality_numpy(fnx.empty_graph(1)) == {0: 1.0}
    with pytest.raises(TypeError):
        nx.katz_centrality_numpy(nx.empty_graph(1))


def test_non_degenerate_current_flow_still_correct():
    # Sanity: on a 3-node path the middle node has the highest current-flow
    # betweenness, ends are 0 — fnx's robustness doesn't distort real cases.
    p3 = fnx.current_flow_betweenness_centrality(fnx.path_graph(3))
    assert p3[1] > p3[0] == pytest.approx(0.0)
    assert p3[1] > p3[2] == pytest.approx(0.0)
    # And it matches networkx on the non-degenerate input.
    n3 = nx.current_flow_betweenness_centrality(nx.path_graph(3))
    assert all(p3[k] == pytest.approx(n3[k]) for k in p3)
