"""Weighted-degree parity against live networkx for FILTERED (subgraph) views.

Kept out of test_io_variants.py deliberately: that file is reserved by another
agent, and these assertions belong to the degree surface rather than to I/O.
"""

import franken_networkx as fnx
import networkx as nx

def test_subgraph_weighted_degree_matches_networkx_including_bail_shapes():
    """Subgraph weighted degree must match networkx, fast path or not.

    br-r37-c1-subwdeg: `_filtered_set_weight` answers weighted degree on a
    node-set subgraph from the PARENT row instead of materialising a filtered
    keydict per neighbour. Two things have to hold, and the second is the one a
    naive test would miss:

    1. it must agree with networkx where it fires, INCLUDING the float
       association -- it walks the parent row in adjacency order precisely
       because a compensated sum is order-dependent; and
    2. it must BAIL to the generic walk where its gates do not hold -- an
       edge_subgraph (non-default edge filter) and a nested subgraph (parent is
       itself a view, not a concrete graph). Those shapes are asserted here so a
       later widening of the gate cannot silently start answering them from the
       wrong row.
    """
    triple = [1e16, 1.0, -1e16]
    assert sum(triple) == 1.0, "fixture no longer discriminates"

    for cls in ("Graph", "DiGraph", "MultiGraph", "MultiDiGraph"):
        expected, actual = getattr(nx, cls)(), getattr(fnx, cls)()
        for graph in (expected, actual):
            graph.add_nodes_from(range(8))
            for index, value in enumerate(triple):
                graph.add_edge(0, index + 1, weight=value)
            graph.add_edge(0, 0, weight=2.5)
            graph.add_edge(2, 3, weight=4)
            graph.add_edge(4, 5)

        keep = [0, 1, 2, 3, 4]
        sub_expected, sub_actual = expected.subgraph(keep), actual.subgraph(keep)
        for node in keep:
            assert sub_actual.degree(node, weight="weight") == sub_expected.degree(
                node, weight="weight"
            ), f"{cls} subgraph degree({node})"
            if cls.endswith("DiGraph"):
                assert sub_actual.in_degree(
                    node, weight="weight"
                ) == sub_expected.in_degree(node, weight="weight"), f"{cls} in({node})"
                assert sub_actual.out_degree(
                    node, weight="weight"
                ) == sub_expected.out_degree(node, weight="weight"), f"{cls} out({node})"
        assert dict(sub_actual.degree(weight="weight")) == dict(
            sub_expected.degree(weight="weight")
        ), f"{cls} subgraph degree view"

        # BAIL SHAPE 1: edge_subgraph carries a non-default edge filter.
        picked_expected = list(expected.edges(keys=True))[:3] if cls.startswith(
            "Multi"
        ) else list(expected.edges)[:3]
        picked_actual = list(actual.edges(keys=True))[:3] if cls.startswith(
            "Multi"
        ) else list(actual.edges)[:3]
        edge_expected = expected.edge_subgraph(picked_expected)
        edge_actual = actual.edge_subgraph(picked_actual)
        for node in edge_expected.nodes:
            assert edge_actual.degree(node, weight="weight") == edge_expected.degree(
                node, weight="weight"
            ), f"{cls} edge_subgraph degree({node})"

        # BAIL SHAPE 2: a nested subgraph's parent is a view, not a graph.
        nested_expected = expected.subgraph(keep).subgraph([0, 1, 2])
        nested_actual = actual.subgraph(keep).subgraph([0, 1, 2])
        for node in (0, 1, 2):
            assert nested_actual.degree(
                node, weight="weight"
            ) == nested_expected.degree(node, weight="weight"), f"{cls} nested({node})"
