"""br-r37-c1-nestedtup: to_nested_tuple child order is nx's
set(T[root]) - {parent} iteration order, NOT str-sorted. The old
sorted(children, key=str) diverged for int-labelled trees (children
{2,10} -> nx [2,10] vs fnx [10,2]). Canonical form sorts the nested
tuples (matched already); non-canonical follows set-iteration order.
"""
import random

import networkx as nx
import pytest

import franken_networkx as fnx


def test_known_int_divergence_case():
    edges = [(0, 2), (0, 10), (10, 5)]
    Tf, Tn = fnx.Graph(edges), nx.Graph(edges)
    assert fnx.to_nested_tuple(Tf, 0) == nx.to_nested_tuple(Tn, 0)
    assert fnx.to_nested_tuple(Tf, 0, canonical_form=True) == nx.to_nested_tuple(
        Tn, 0, canonical_form=True
    )


@pytest.mark.parametrize("canonical", [False, True])
def test_random_int_tree_corpus(canonical):
    rnd = random.Random(21)
    for trial in range(20):
        n = rnd.randrange(3, 18)
        nodes = list(range(n))
        rnd.shuffle(nodes)
        Tf, Tn = fnx.Graph(), nx.Graph()
        for i in range(1, n):
            p = nodes[rnd.randrange(i)]
            Tf.add_edge(p, nodes[i])
            Tn.add_edge(p, nodes[i])
        root = nodes[0]
        assert fnx.to_nested_tuple(Tf, root, canonical_form=canonical) == nx.to_nested_tuple(
            Tn, root, canonical_form=canonical
        ), trial


@pytest.mark.parametrize("canonical", [False, True])
def test_string_tree(canonical):
    edges = [("r", "b"), ("r", "a"), ("b", "z"), ("b", "c")]
    Tf, Tn = fnx.Graph(edges), nx.Graph(edges)
    assert fnx.to_nested_tuple(Tf, "r", canonical_form=canonical) == nx.to_nested_tuple(
        Tn, "r", canonical_form=canonical
    )


@pytest.mark.parametrize("root", [0, "missing"])
def test_directed_input_rejects_before_root_lookup(root):
    Tf = fnx.DiGraph([(0, 1)])
    Tn = nx.DiGraph([(0, 1)])

    with pytest.raises(nx.NetworkXNotImplemented) as fnx_exc:
        fnx.to_nested_tuple(Tf, root)
    with pytest.raises(nx.NetworkXNotImplemented) as nx_exc:
        nx.to_nested_tuple(Tn, root)
    assert (
        str(fnx_exc.value)
        == str(nx_exc.value)
        == "not implemented for directed type"
    )
