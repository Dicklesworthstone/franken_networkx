"""Coverage for the last untested deterministic shared functions.

Of 759 functions shared with networkx, these were among the few without
dedicated coverage: ``is_valid_joint_degree``,
``is_valid_directed_joint_degree`` and ``prefix_tree_recursive``. Combines
differential parity vs networkx with metamorphic checks.

br-r37-c1-plg5i
"""

from __future__ import annotations

import random
from collections import defaultdict

import pytest
import networkx as nx
import franken_networkx as fnx


def _joint_degree(g):
    jdd = defaultdict(lambda: defaultdict(int))
    for u, v in g.edges():
        du, dv = g.degree(u), g.degree(v)
        jdd[du][dv] += 1
        jdd[dv][du] += 1
    return {k: dict(v) for k, v in jdd.items()}


@pytest.mark.parametrize("seed", range(40))
def test_is_valid_joint_degree_matches_networkx(seed):
    g = nx.gnp_random_graph(random.Random(seed).randint(5, 10), 0.4, seed=seed)
    jdd = _joint_degree(g)
    assert fnx.is_valid_joint_degree(jdd) == nx.is_valid_joint_degree(jdd)
    # Metamorphic: a real graph's joint degree distribution is always valid.
    if g.number_of_edges() > 0:
        assert fnx.is_valid_joint_degree(jdd)


@pytest.mark.parametrize("seed", range(30))
def test_is_valid_directed_joint_degree_matches_networkx(seed):
    g = nx.gnp_random_graph(
        random.Random(seed).randint(5, 9), 0.35, seed=seed, directed=True
    )
    if g.number_of_edges() == 0:
        pytest.skip("no edges")
    nkk = defaultdict(lambda: defaultdict(int))
    for u, v in g.edges():
        nkk[g.out_degree(u)][g.in_degree(v)] += 1
    nkk = {k: dict(v) for k, v in nkk.items()}
    in_deg = [g.in_degree(n) for n in g]
    out_deg = [g.out_degree(n) for n in g]
    assert fnx.is_valid_directed_joint_degree(in_deg, out_deg, nkk) == (
        nx.is_valid_directed_joint_degree(in_deg, out_deg, nkk)
    )


@pytest.mark.parametrize("seed", range(40))
def test_prefix_tree_recursive_matches_prefix_tree(seed):
    rng = random.Random(seed)
    paths = [
        [rng.choice("abc") for _ in range(rng.randint(1, 4))]
        for _ in range(rng.randint(1, 4))
    ]
    t1 = fnx.prefix_tree(paths)
    t2 = fnx.prefix_tree_recursive(paths)
    sig1 = sorted((str(n), str(d.get("source"))) for n, d in t1.nodes(data=True))
    sig2 = sorted((str(n), str(d.get("source"))) for n, d in t2.nodes(data=True))
    assert sig1 == sig2
    assert sorted(t1.edges()) == sorted(t2.edges())
    # And both agree with networkx's recursive builder.
    tn = nx.prefix_tree_recursive(paths)
    assert sorted((str(n), str(d.get("source"))) for n, d in tn.nodes(data=True)) == sig2
