"""A node's hash can change the edges used by the current PageRank call."""

import networkx as nx
import pytest

import franken_networkx as fnx


@pytest.mark.parametrize("graph_type", ["Graph", "DiGraph"])
@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("action", ["add-edge", "remove-edge", "raise"])
def test_pagerank_reads_edges_after_node_validation(graph_type, warm, action):
    def run(module):
        graph = getattr(module, graph_type)()
        armed = False

        class Node(int):
            def __hash__(self):
                nonlocal armed
                if armed:
                    armed = False
                    if action == "raise":
                        raise LookupError("node validation")
                    if action == "add-edge":
                        graph.add_edge(0, 2, weight=4)
                    else:
                        graph.remove_edge(0, 1)
                return int.__hash__(self)

        nodes = [Node(i) for i in range(4)]
        graph.add_edges_from(zip(nodes, nodes[1:] + nodes[:1]))
        if warm:
            module.pagerank(graph)
        armed = True
        if action == "raise":
            with pytest.raises(LookupError, match="node validation"):
                module.pagerank(graph)
            graph.add_edge(0, 2)
        scores = module.pagerank(graph)
        assert not armed
        return list(graph.edges()), list(scores), scores

    expected_edges, expected_nodes, expected_scores = run(nx)
    edges, nodes, scores = run(fnx)
    assert edges == expected_edges
    assert nodes == expected_nodes
    assert scores == pytest.approx(expected_scores, abs=1e-12, rel=1e-12)
