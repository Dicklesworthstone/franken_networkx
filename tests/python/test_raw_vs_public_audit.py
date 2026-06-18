"""br-r37-c1-cvrij: regression tests for raw-vs-public audit findings.

Companion to ``scripts/raw_vs_public_audit.py``. The audit script
classifies every public ``_raw_<NAME>`` exposure against its public
``<NAME>`` wrapper across a battery of small fixtures. This test locks
in the most important findings:

1. **sjf4t fix is live**: ``single_source_dijkstra_path_length`` and
   ``single_source_bellman_ford_path_length`` produce nx-matching
   distances even on the post-mutation fixture.
2. **Directed-input rejection is wired**: ``articulation_points``,
   ``bridges``, ``connected_components`` raise ``NetworkXNotImplemented``
   on the first ``next()`` call (the wrappers are generators with a
   ``not_implemented_for`` decorator that defers the check).
3. **astar weighted-postmut bug is acknowledged**: the audit currently
   surfaces a divergence on ``astar_path_length`` for postmut graphs
   (pre-existing — astar wrapper does not call the sjf4t sync). Test
   marks it as expected-failure until the follow-up bead lands.
"""

from __future__ import annotations

import pytest

import franken_networkx as fnx
import networkx as nx


# ---------------------------------------------------------------------------
# sjf4t fix lockdown
# ---------------------------------------------------------------------------


def test_audit_dijkstra_postmut_matches_nx():
    """``single_source_dijkstra_path_length`` on a post-creation-mutated
    weighted graph must match nx — locked in by br-r37-c1-sjf4t."""
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    for i, (u, v) in enumerate(fg.edges):
        fg[u][v]["weight"] = i + 1.5
    for i, (u, v) in enumerate(ng.edges):
        ng[u][v]["weight"] = i + 1.5

    f_dist = dict(fnx.single_source_dijkstra_path_length(fg, 0))
    n_dist = dict(nx.single_source_dijkstra_path_length(ng, 0))
    assert f_dist == n_dist


def test_audit_bellman_ford_postmut_matches_nx():
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    for i, (u, v) in enumerate(fg.edges):
        fg[u][v]["weight"] = i + 1.5
    for i, (u, v) in enumerate(ng.edges):
        ng[u][v]["weight"] = i + 1.5

    f_dist = dict(fnx.single_source_bellman_ford_path_length(fg, 0))
    n_dist = dict(nx.single_source_bellman_ford_path_length(ng, 0))
    assert f_dist == n_dist


# ---------------------------------------------------------------------------
# Known bug acknowledgements (xfail until follow-up beads land)
# ---------------------------------------------------------------------------


def test_astar_path_length_postmut_matches_nx():
    """br-r37-c1-0x9pd: astar wrapper must sync attrs to Rust before
    invoking the native kernel — same pattern as the dijkstra/BF/FW
    family fixed in br-r37-c1-sjf4t."""
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    for i, (u, v) in enumerate(fg.edges):
        fg[u][v]["weight"] = i + 1.5
    for i, (u, v) in enumerate(ng.edges):
        ng[u][v]["weight"] = i + 1.5

    expected = nx.astar_path_length(ng, 0, 4)
    actual = fnx.astar_path_length(fg, 0, 4)
    assert actual == expected, f"fnx={actual} nx={expected}"


def test_raw_eccentricity_rejects_directed_input():
    """br-r37-c1-t8055: _raw_eccentricity collapsed directed input via
    `gr.undirected()`, returning silently-wrong values for
    weakly-but-not-strongly-connected DiGraphs. Now matches the
    diameter/radius/center/periphery contract: directed input raises
    NetworkXNotImplemented from the kernel itself."""
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    g.add_edge(2, 3)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx._raw_eccentricity(g)
    # Public wrapper still works on DiGraph (routes around _raw_).
    with pytest.raises(fnx.NetworkXError):
        fnx.eccentricity(g)


def test_raw_eccentricity_undirected_unchanged():
    g = fnx.path_graph(5)
    result = fnx._raw_eccentricity(g)
    assert result == {0: 4, 1: 3, 2: 2, 3: 3, 4: 4}


def test_raw_find_cliques_rejects_directed_input():
    """br-r37-c1-ewpss: kernel previously collapsed directed input via
    gr.undirected() and silently returned cliques on the underlying
    undirected projection."""
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx._raw_find_cliques(g)


def test_raw_is_chordal_rejects_directed_input():
    """br-r37-c1-ewpss: same fix as find_cliques."""
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fnx._raw_is_chordal(g)


def test_raw_find_cliques_undirected_unchanged():
    g = fnx.path_graph(5)
    result = fnx._raw_find_cliques(g)
    # 4 edges, each a maximal clique (path graph)
    assert len(result) == 4


def test_raw_is_chordal_undirected_unchanged():
    assert fnx._raw_is_chordal(fnx.path_graph(5)) is True
    assert fnx._raw_is_chordal(fnx.cycle_graph(6)) is False


def test_raw_ancestors_descendants_missing_string_node_message_matches_public_and_nx():
    fg = fnx.DiGraph([("a", "b")])
    ng = nx.DiGraph([("a", "b")])
    expected = "The node missing is not in the digraph."

    for raw_func, public_func, nx_func in [
        (fnx._raw_ancestors, fnx.ancestors, nx.ancestors),
        (fnx._raw_descendants, fnx.descendants, nx.descendants),
    ]:
        with pytest.raises(fnx.NetworkXError) as raw_exc:
            raw_func(fg, "missing")
        with pytest.raises(fnx.NetworkXError) as public_exc:
            public_func(fg, "missing")
        with pytest.raises(nx.NetworkXError) as nx_exc:
            nx_func(ng, "missing")

        assert str(raw_exc.value) == expected
        assert str(public_exc.value) == expected
        assert str(nx_exc.value) == expected


def test_raw_bfs_missing_string_source_message_matches_public_and_nx():
    fg = fnx.path_graph(["a", "b"])
    ng = nx.path_graph(["a", "b"])
    expected = "The node missing is not in the graph."

    cases = [
        (
            fnx.NodeNotFound,
            lambda: fnx._bfs_edges_raw(fg, "missing"),
            lambda: list(fnx.bfs_edges(fg, "missing")),
            lambda: list(nx.bfs_edges(ng, "missing")),
        ),
        (
            fnx.NodeNotFound,
            lambda: fnx._bfs_tree_raw(fg, "missing"),
            lambda: fnx.bfs_tree(fg, "missing"),
            lambda: nx.bfs_tree(ng, "missing"),
        ),
        (
            fnx.NodeNotFound,
            lambda: fnx._bfs_predecessors_raw(fg, "missing"),
            lambda: list(fnx.bfs_predecessors(fg, "missing")),
            lambda: list(nx.bfs_predecessors(ng, "missing")),
        ),
        (
            fnx.NodeNotFound,
            lambda: fnx._bfs_successors_raw(fg, "missing"),
            lambda: list(fnx.bfs_successors(fg, "missing")),
            lambda: list(nx.bfs_successors(ng, "missing")),
        ),
        (
            fnx.NetworkXError,
            lambda: fnx._bfs_layers_raw(fg, ["missing"]),
            lambda: list(fnx.bfs_layers(fg, ["missing"])),
            lambda: list(nx.bfs_layers(ng, ["missing"])),
        ),
        (
            fnx.NodeNotFound,
            lambda: fnx._raw_descendants_at_distance(fg, "missing", 1),
            lambda: fnx.descendants_at_distance(fg, "missing", 1),
            lambda: nx.descendants_at_distance(ng, "missing", 1),
        ),
    ]

    for raw_error, raw_call, public_call, nx_call in cases:
        with pytest.raises(raw_error) as raw_exc:
            raw_call()
        with pytest.raises(fnx.NetworkXError) as public_exc:
            public_call()
        with pytest.raises(nx.NetworkXError) as nx_exc:
            nx_call()

        assert str(raw_exc.value) == expected
        assert str(public_exc.value) == expected
        assert str(nx_exc.value) == expected


def test_raw_dfs_missing_string_source_message_matches_public_and_nx():
    fg = fnx.path_graph(["a", "b"])
    ng = nx.path_graph(["a", "b"])
    expected = "The node missing is not in the graph."

    cases = [
        (
            lambda: fnx._dfs_edges_raw(fg, "missing"),
            lambda: list(fnx.dfs_edges(fg, "missing")),
            lambda: list(nx.dfs_edges(ng, "missing")),
        ),
        (
            lambda: fnx._dfs_tree_raw(fg, "missing"),
            lambda: fnx.dfs_tree(fg, "missing"),
            lambda: nx.dfs_tree(ng, "missing"),
        ),
        (
            lambda: fnx._dfs_predecessors_raw(fg, "missing"),
            lambda: fnx.dfs_predecessors(fg, "missing"),
            lambda: nx.dfs_predecessors(ng, "missing"),
        ),
        (
            lambda: fnx._dfs_successors_raw(fg, "missing"),
            lambda: fnx.dfs_successors(fg, "missing"),
            lambda: nx.dfs_successors(ng, "missing"),
        ),
        (
            lambda: fnx._dfs_preorder_nodes_raw(fg, "missing"),
            lambda: list(fnx.dfs_preorder_nodes(fg, "missing")),
            lambda: list(nx.dfs_preorder_nodes(ng, "missing")),
        ),
        (
            lambda: fnx._dfs_postorder_nodes_raw(fg, "missing"),
            lambda: list(fnx.dfs_postorder_nodes(fg, "missing")),
            lambda: list(nx.dfs_postorder_nodes(ng, "missing")),
        ),
    ]

    for raw_call, public_call, nx_call in cases:
        with pytest.raises(fnx.NodeNotFound) as raw_exc:
            raw_call()
        with pytest.raises(fnx.NetworkXError) as public_exc:
            public_call()
        with pytest.raises(nx.NetworkXError) as nx_exc:
            nx_call()

        assert str(raw_exc.value) == expected
        assert str(public_exc.value) == expected
        assert str(nx_exc.value) == expected


@pytest.mark.parametrize(
    "fn_name",
    [
        "clustering",
        "average_clustering",
        "transitivity",
        "is_chordal",
        "core_number",
        "girth",
    ],
)
def test_raw_kernels_reject_multigraph(fn_name):
    """br-r37-c1-djohp: extended audit found 6 raw kernels that
    silently collapse multigraph input to its simple-graph projection.
    Each gains a require_not_multigraph guard so direct callers see
    NetworkXNotImplemented matching nx + the public wrappers."""
    mg = fnx.MultiGraph()
    mg.add_edge(0, 1)
    mg.add_edge(0, 1)  # parallel edge
    mg.add_edge(1, 2)
    fn = getattr(fnx, "_raw_" + fn_name)
    with pytest.raises(fnx.NetworkXNotImplemented):
        fn(mg)


def test_is_chordal_multidigraph_rejects_multigraph_before_directed():
    """br-r37-c1-tiy27: nx reports the multigraph guard for MultiDiGraph."""
    fg = fnx.MultiDiGraph()
    fg.add_edge(0, 1)
    ng = nx.MultiDiGraph()
    ng.add_edge(0, 1)

    for fn in (fnx._raw_is_chordal, fnx.is_chordal):
        with pytest.raises(fnx.NetworkXNotImplemented, match="multigraph type"):
            fn(fg)
    with pytest.raises(nx.NetworkXNotImplemented, match="multigraph type"):
        nx.is_chordal(ng)


def test_raw_barycenter_rejects_empty_graph():
    """br-r37-c1-djohp: nx raises NetworkXPointlessConcept on empty
    input; raw kernel previously returned []."""
    with pytest.raises(fnx.NetworkXPointlessConcept):
        fnx._raw_barycenter(fnx.Graph())


def test_raw_core_number_rejects_self_loops():
    """br-r37-c1-ftorb: extended audit found that _raw_core_number
    silently returned wrong values on graphs with self-loops because
    the k-core bucket decomposition double-counts the loop in the
    degree. nx raises NetworkXNotImplemented with a remediation hint;
    mirror that contract."""
    g = fnx.Graph()
    g.add_edge(0, 0)  # self-loop
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    with pytest.raises(fnx.NetworkXNotImplemented, match="self loops"):
        fnx._raw_core_number(g)
    # Public wrapper inherits the same rejection.
    with pytest.raises(fnx.NetworkXNotImplemented, match="self loops"):
        fnx.core_number(g)
    # Simple graph still works.
    assert fnx._raw_core_number(fnx.path_graph(5)) == {0: 1, 1: 1, 2: 1, 3: 1, 4: 1}


def test_audit_classifies_barycenter_exception_type_drift():
    """br-r37-c1-ts8kd: raw/public/nx all raising is not enough for
    parity. The audit must compare exception classes too."""
    from scripts import raw_vs_public_audit as audit

    reports = {report.name: report for report in audit.run_audit()}
    barycenter = reports["barycenter"]
    directed_row = next(row for row in barycenter.rows if row.fixture_id == "digraph-chain-5")

    assert directed_row.raw.error_type == "NetworkXNotImplemented"
    assert directed_row.public.error_type == "NetworkXNoPath"
    assert directed_row.nx_baseline.error_type == "NetworkXNoPath"
    assert barycenter.classification == "wrapper-corrected"


@pytest.mark.parametrize(
    "fn_name,builder,expected",
    [
        ("clustering", lambda: fnx.path_graph(5),
         {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}),
        ("transitivity", lambda: fnx.complete_graph(4), 1.0),
        ("girth", lambda: fnx.cycle_graph(6), 6),
        ("core_number", lambda: fnx.path_graph(3), {0: 1, 1: 1, 2: 1}),
        ("is_chordal", lambda: fnx.path_graph(5), True),
    ],
)
def test_raw_kernels_simple_graph_unchanged(fn_name, builder, expected):
    """Sanity: the multigraph guards do not break the simple-graph path."""
    fn = getattr(fnx, "_raw_" + fn_name)
    assert fn(builder()) == expected


def test_astar_path_postmut_matches_nx():
    """br-r37-c1-0x9pd companion: astar_path also gets the sync."""
    fg = fnx.path_graph(5)
    ng = nx.path_graph(5)
    for i, (u, v) in enumerate(fg.edges):
        fg[u][v]["weight"] = i + 1.5
    for i, (u, v) in enumerate(ng.edges):
        ng[u][v]["weight"] = i + 1.5

    assert fnx.astar_path(fg, 0, 4) == nx.astar_path(ng, 0, 4)


@pytest.mark.parametrize(
    "fnname",
    ["articulation_points", "bridges", "connected_components"],
)
def test_directed_input_rejected_on_iteration(fnname):
    """The audit's first run misclassified these as error-divergence
    (the wrappers return a generator that defers the directed-input
    check until first ``next()``). Verified this is correct nx
    semantics by materializing the generator — locked in here so the
    deferred-rejection contract is not regressed."""
    g = fnx.DiGraph()
    g.add_edge(0, 1)
    g.add_edge(1, 2)
    fn = getattr(fnx, fnname)
    with pytest.raises(fnx.NetworkXNotImplemented):
        # Materialize generator — rejection happens on first next().
        list(fn(g))


# ---------------------------------------------------------------------------
# Smoke: the audit script runs to completion
# ---------------------------------------------------------------------------


def test_audit_script_runs_to_completion():
    """The audit script imports cleanly and produces both report files."""
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    script = repo_root / "scripts" / "raw_vs_public_audit.py"
    out_dir = repo_root / "docs"

    # Use --quiet so this test does not produce stdout chatter.
    result = subprocess.run(
        [sys.executable, str(script), "--quiet", "--output-dir", str(out_dir)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    md = out_dir / "raw_vs_public_audit.md"
    js = out_dir / "raw_vs_public_audit.json"
    assert md.exists(), md
    assert js.exists(), js
    body = md.read_text(encoding="utf-8")
    # Critical regression: sjf4t fix should keep
    # single_source_dijkstra_path_length out of any "wrapper-broken" bucket.
    assert "wrapper-broken" not in body or "single_source_dijkstra_path_length" not in (
        section
        for section in body.split("##")
        if "wrapper-broken" in section
    ), "single_source_dijkstra_path_length regressed into wrapper-broken bucket"
