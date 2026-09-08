"""Comprehensive test suite for FrankenNetworkX runtime compatibility modes.

Validates:
1. Process-wide and thread-local mode switches (fnx.config.compatibility_mode,
   with fnx.config(compatibility_mode="hardened"):, with fnx.compatibility_mode("hardened"):).
2. Function-level mode kwargs across all read/parse entry points (read_edgelist,
   read_adjlist, read_graphml, read_gml, read_gexf, read_json_graph, node_link_graph).
3. Graph properties (G.mode, G.compatibility_mode) and DecisionRecord ledger
   drainability (G.decision_records(), G.drain_decision_records(), fnx.decision_records(G),
   fnx.drain_decision_records(G)).
4. 24 well-formed fixtures asserting exact parity between Strict and Hardened modes.
5. 24 malformed fixtures asserting fail-closed under Strict and bounded recovery under Hardened.
6. Planted negative asserting unknown incompatible features fail closed even in Hardened mode.
"""

import io
import pytest
import franken_networkx as fnx


# ===========================================================================
# 1. Mode Configuration and Switching Tests
# ===========================================================================


def test_mode_switch_global():
    """Verify global compatibility mode configuration via fnx.config and helpers."""
    original = fnx.get_compatibility_mode()
    assert original == "strict"
    assert fnx.config.compatibility_mode == "strict"
    assert fnx.config["compatibility_mode"] == "strict"

    try:
        fnx.config.compatibility_mode = "hardened"
        assert fnx.get_compatibility_mode() == "hardened"
        assert fnx.config.compatibility_mode == "hardened"
        assert fnx.config["compatibility_mode"] == "hardened"

        G = fnx.Graph()
        assert G.mode == "hardened"
        assert G.compatibility_mode == "hardened"

        fnx.config["compatibility_mode"] = "strict"
        assert fnx.get_compatibility_mode() == "strict"
        assert fnx.config.compatibility_mode == "strict"

        fnx.set_compatibility_mode("hardened")
        assert fnx.get_compatibility_mode() == "hardened"
        fnx.set_compatibility_mode("strict")
        assert fnx.get_compatibility_mode() == "strict"

        with pytest.raises(ValueError, match="invalid compatibility mode"):
            fnx.config.compatibility_mode = "nonexistent_mode"

        with pytest.raises(ValueError, match="invalid compatibility mode"):
            fnx.set_compatibility_mode("invalid_mode")
    finally:
        fnx.set_compatibility_mode("strict")


def test_mode_switch_context_managers():
    """Verify scoped compatibility mode overriding via context managers."""
    assert fnx.get_compatibility_mode() == "strict"

    # Context manager: with fnx.config(compatibility_mode="hardened")
    with fnx.config(compatibility_mode="hardened"):
        assert fnx.get_compatibility_mode() == "hardened"
        assert fnx.config.compatibility_mode == "hardened"
        G = fnx.Graph()
        assert G.mode == "hardened"
        DG = fnx.DiGraph()
        assert DG.mode == "hardened"
        MG = fnx.MultiGraph()
        assert MG.mode == "hardened"
        MDG = fnx.MultiDiGraph()
        assert MDG.mode == "hardened"

    assert fnx.get_compatibility_mode() == "strict"
    assert fnx.config.compatibility_mode == "strict"

    # Context manager: with fnx.compatibility_mode("hardened")
    with fnx.compatibility_mode("hardened"):
        assert fnx.get_compatibility_mode() == "hardened"
        G2 = fnx.Graph()
        assert G2.mode == "hardened"

    assert fnx.get_compatibility_mode() == "strict"

    # Combined with standard NetworkX config options
    with fnx.config(backend_priority=["franken_networkx"], compatibility_mode="hardened"):
        assert fnx.get_compatibility_mode() == "hardened"
        assert "franken_networkx" in fnx.config.backend_priority.algos

    assert fnx.get_compatibility_mode() == "strict"

    with pytest.raises(ValueError, match="invalid compatibility mode"):
        with fnx.config(compatibility_mode="bogus"):
            pass

    with pytest.raises(ValueError, match="invalid compatibility mode"):
        with fnx.compatibility_mode("bogus"):
            pass


def test_graph_constructors_and_audit_ledger():
    """Verify Graph, DiGraph, MultiGraph, MultiDiGraph ledger getters and draining."""
    for cls in (fnx.Graph, fnx.DiGraph, fnx.MultiGraph, fnx.MultiDiGraph):
        # Strict mode
        g_strict = cls()
        assert g_strict.mode == "strict"
        assert g_strict.compatibility_mode == "strict"
        assert g_strict.decision_records() == []
        assert fnx.decision_records(g_strict) == []
        assert g_strict.drain_decision_records() == []
        assert fnx.drain_decision_records(g_strict) == []

        # Hardened mode
        with fnx.compatibility_mode("hardened"):
            g_hardened = cls()
            assert g_hardened.mode == "hardened"
            assert g_hardened.compatibility_mode == "hardened"
            assert g_hardened.decision_records() == []


def test_constructor_kwargs_not_shadowed():
    """Verify Graph(**attr) keeps standard nx kwargs semantics and does not shadow mode."""
    G = fnx.Graph(name="test_graph", custom_attr=123)
    assert G.graph["name"] == "test_graph"
    assert G.graph["custom_attr"] == 123
    assert G.mode == "strict"


# ===========================================================================
# 2. 24 Well-Formed Fixtures (Exact Parity between Strict and Hardened)
# ===========================================================================

WELL_FORMED_FIXTURES = [
    # --- Edgelist (4) ---
    ("edgelist", "# comment only\n"),
    ("edgelist", "0 1\n"),
    ("edgelist", "0 1\n1 2\n2 0\n"),
    ("edgelist", "0 1 weight=2.5\n1 2 weight=4.0\n"),
    # --- Adjlist (4) ---
    ("adjlist", "# empty adjlist\n"),
    ("adjlist", "0 1 2 3\n1\n2\n3\n"),
    ("adjlist", "0 1\n1 2\n2 3\n3\n"),
    ("adjlist", "0 1\n1\n2 3\n3\n"),
    # --- GraphML (5) ---
    (
        "graphml",
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        '  <graph edgedefault="undirected">\n'
        '    <node id="n0"/>\n'
        '    <node id="n1"/>\n'
        '    <edge source="n0" target="n1"/>\n'
        "  </graph>\n"
        "</graphml>",
    ),
    (
        "graphml",
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        '  <graph edgedefault="directed">\n'
        '    <node id="n0"/>\n'
        '    <node id="n1"/>\n'
        '    <edge source="n0" target="n1"/>\n'
        "  </graph>\n"
        "</graphml>",
    ),
    (
        "graphml",
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        '  <key id="d0" for="node" attr.name="color" attr.type="string"/>\n'
        '  <graph edgedefault="undirected">\n'
        '    <node id="n0"><data key="d0">green</data></node>\n'
        '    <node id="n1"/>\n'
        "  </graph>\n"
        "</graphml>",
    ),
    (
        "graphml",
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        '  <key id="d1" for="edge" attr.name="weight" attr.type="double"/>\n'
        '  <graph edgedefault="undirected">\n'
        '    <node id="0"/>\n'
        '    <node id="1"/>\n'
        '    <edge source="0" target="1"><data key="d1">3.14</data></edge>\n'
        "  </graph>\n"
        "</graphml>",
    ),
    (
        "graphml",
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n'
        '  <graph edgedefault="undirected">\n'
        '    <node id="a"/>\n'
        '    <node id="b"/>\n'
        '    <node id="c"/>\n'
        '    <edge source="a" target="b"/>\n'
        '    <edge source="b" target="c"/>\n'
        '    <edge source="c" target="a"/>\n'
        "  </graph>\n"
        "</graphml>",
    ),
    # --- GML (4) ---
    (
        "gml",
        'graph [\n  node [\n    id 0\n    label "0"\n  ]\n  node [\n    id 1\n    label "1"\n  ]\n  edge [\n    source 0\n    target 1\n  ]\n]',
    ),
    (
        "gml",
        'graph [\n  directed 1\n  node [\n    id 0\n    label "0"\n  ]\n  node [\n    id 1\n    label "1"\n  ]\n  edge [\n    source 0\n    target 1\n  ]\n]',
    ),
    (
        "gml",
        'graph [\n  node [\n    id 0\n    label "0"\n  ]\n  node [\n    id 1\n    label "1"\n  ]\n  edge [\n    source 0\n    target 1\n    weight 5\n  ]\n]',
    ),
    (
        "gml",
        'graph [\n  node [\n    id 0\n    label "0"\n  ]\n  node [\n    id 1\n    label "1"\n  ]\n  node [\n    id 2\n    label "2"\n  ]\n  edge [\n    source 0\n    target 1\n  ]\n  edge [\n    source 1\n    target 2\n  ]\n]',
    ),
    # --- GEXF (3) ---
    (
        "gexf",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n'
        '  <graph mode="static" defaultedgetype="undirected">\n'
        "    <nodes>\n"
        '      <node id="0" label="Node 0"/>\n'
        '      <node id="1" label="Node 1"/>\n'
        "    </nodes>\n"
        "    <edges>\n"
        '      <edge id="0" source="0" target="1"/>\n'
        "    </edges>\n"
        "  </graph>\n"
        "</gexf>",
    ),
    (
        "gexf",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n'
        '  <graph mode="static" defaultedgetype="directed">\n'
        "    <nodes>\n"
        '      <node id="0" label="Node 0"/>\n'
        '      <node id="1" label="Node 1"/>\n'
        "    </nodes>\n"
        "    <edges>\n"
        '      <edge id="0" source="0" target="1"/>\n'
        "    </edges>\n"
        "  </graph>\n"
        "</gexf>",
    ),
    (
        "gexf",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n'
        '  <graph mode="static" defaultedgetype="undirected">\n'
        "    <nodes>\n"
        '      <node id="a" label="Node A"/>\n'
        '      <node id="b" label="Node B"/>\n'
        '      <node id="c" label="Node C"/>\n'
        "    </nodes>\n"
        "    <edges>\n"
        '      <edge id="0" source="a" target="b"/>\n'
        '      <edge id="1" source="b" target="c"/>\n'
        "    </edges>\n"
        "  </graph>\n"
        "</gexf>",
    ),
    # --- JSON Graph / node_link (4) ---
    ("json_graph", '{"nodes": [], "edges": [], "mode": "strict"}'),
    (
        "json_graph",
        '{"mode": "strict", "directed": false, "nodes": ["0", "1"], "edges": [{"left": "0", "right": "1", "attrs": {}}]}',
    ),
    (
        "json_graph",
        '{"mode": "strict", "directed": true, "nodes": ["a", "b"], "edges": [{"left": "a", "right": "b", "attrs": {}}]}',
    ),
    (
        "json_graph",
        '{"mode": "strict", "directed": false, "nodes": ["u", "v", "w"], "edges": [{"left": "u", "right": "v", "attrs": {"w": 1.0}}, {"left": "v", "right": "w", "attrs": {}}]}',
    ),
]


def _read_by_fmt(fmt, payload, mode):
    bio = io.StringIO(payload)
    if fmt == "edgelist":
        return fnx.read_edgelist(bio, mode=mode)
    elif fmt == "adjlist":
        return fnx.read_adjlist(bio, mode=mode)
    elif fmt == "graphml":
        return fnx.read_graphml(bio, mode=mode)
    elif fmt == "gml":
        return fnx.read_gml(bio, mode=mode)
    elif fmt == "gexf":
        return fnx.read_gexf(bio, mode=mode)
    elif fmt == "json_graph":
        return fnx.read_json_graph(bio, mode=mode)
    raise ValueError(f"unknown format {fmt}")


@pytest.mark.parametrize(
    "idx, fmt, payload",
    [(i, f, p) for i, (f, p) in enumerate(WELL_FORMED_FIXTURES)],
)
def test_well_formed_parity_fixtures(idx, fmt, payload):
    """Assert exact structural and behavioral parity between Strict and Hardened on 24 well-formed fixtures."""
    g_strict = _read_by_fmt(fmt, payload, mode="strict")
    g_hardened = _read_by_fmt(fmt, payload, mode="hardened")

    assert g_strict.number_of_nodes() == g_hardened.number_of_nodes(), f"node count mismatch on fixture {idx}"
    assert g_strict.number_of_edges() == g_hardened.number_of_edges(), f"edge count mismatch on fixture {idx}"
    assert set(g_strict.nodes()) == set(g_hardened.nodes()), f"node set mismatch on fixture {idx}"
    assert g_strict.is_directed() == g_hardened.is_directed(), f"directedness mismatch on fixture {idx}"

    assert g_strict.mode == "strict"
    assert g_hardened.mode == "hardened"

    # Well-formed inputs require zero repair/fail decisions (all decisions must be allow)
    strict_records = g_strict.decision_records()
    hardened_records = g_hardened.decision_records()
    assert all(r["action"] == "allow" for r in strict_records)
    assert all(r["mode"] == "strict" for r in strict_records)
    assert all(r["action"] == "allow" for r in hardened_records)
    assert all(r["mode"] == "hardened" for r in hardened_records)


# ===========================================================================
# 3. 24 Malformed Fixtures (Fail-Closed under Strict, Bounded Recovery under Hardened)
# ===========================================================================

MALFORMED_FIXTURES = [
    # --- Malformed Edgelist (5) ---
    ("edgelist", "incomplete_single_token\n"),
    ("edgelist", "0 1\nincomplete_node\n2 3\n"),
    ("edgelist", "0\n1\n2\n"),
    ("edgelist", "0 1\nbad_edge_line\n"),
    ("edgelist", "0 1 2 3 extra\n"),
    # --- Malformed GraphML (5) ---
    ("graphml", '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><graph><node id="0"/></graph></graphml>'),  # missing edgedefault
    ("graphml", '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><graph edgedefault="bogus"><node id="0"/></graph></graphml>'),  # invalid edgedefault
    ("graphml", '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><key id="d0" for="node"/><graph edgedefault="undirected"><node id="0"/></graph></graphml>'),  # key missing attr.name
    ("graphml", '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><key attr.name="color"/><graph edgedefault="undirected"><node id="0"/></graph></graphml>'),  # key missing id
    ("graphml", '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><graph edgedefault="undirected"><node id="0"/><hyperedge/></graph></graphml>'),  # unsupported hyperedge
    # --- Malformed GML (5) ---
    ("gml", 'graph [\n  node [\n    id 0\n  ]\n  node [\n    id 0\n  ]\n]'),  # duplicate node id
    ("gml", 'graph [\n  node [\n    id 0\n'),                                # unclosed bracket
    ("gml", 'graph [\n  node [\n    id 0\n  ]\n]\n]'),                        # stray ']' token
    ("gml", 'graph [\n  node [\n    id 0\n  ]\n  node [\n    id 1\n  ]\n  edge [\n    source 0\n]'),  # edge missing target
    ("gml", 'graph [\n  node [\n    id 0\n  ]\n  node [\n    id 1\n  ]\n  edge [\n    source 0\n    target 1\n  ]\n  edge [\n    source 0\n    target 1\n  ]\n]'),  # duplicate edge
    # --- Malformed GEXF (5) ---
    ("gexf", '<?xml version="1.0" encoding="UTF-8"?>\n<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n  <graph defaultedgetype="bogus">\n    <nodes><node id="0"/></nodes>\n  </graph>\n</gexf>'),  # invalid defaultedgetype
    ("gexf", '<?xml version="1.0" encoding="UTF-8"?>\n<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n  <graph defaultedgetype="undirected">\n    <nodes><node label="NoId"/></nodes>\n  </graph>\n</gexf>'),  # node missing id
    ("gexf", '<?xml version="1.0" encoding="UTF-8"?>\n<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n  <graph defaultedgetype="undirected">\n    <nodes><node id="0"/></nodes>\n    <edges><edge id="e1" source="0"/></edges>\n  </graph>\n</gexf>'),  # edge missing target
    ("gexf", '<?xml version="1.0" encoding="UTF-8"?>\n<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n  <graph defaultedgetype="undirected">\n    <nodes><node id="0"/><node id="1"/></nodes>\n    <edges><edge id="e1" source="0" target="1"/><edge id="e2" source="0" target="1"/></edges>\n  </graph>\n</gexf>'),  # duplicate edge
    ("gexf", '<?xml version="1.0" encoding="UTF-8"?>\n<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n  <graph defaultedgetype="undirected">\n    <attributes class="node"><attribute/></attributes>\n    <nodes><node id="0"/></nodes>\n  </graph>\n</gexf>'),  # attribute missing id/title
    # --- Malformed JSON Graph (4) ---
    ("json_graph", '{not valid json'),                                        # corrupt syntax
    ("json_graph", '{"nodes": [ {"id": 1}, incomplete'),                     # unclosed json
    ("json_graph", '{"mode": "strict", "nodes": ["0", "1"], "edges": ["not_a_record"]}'),  # invalid edge record
    ("json_graph", '{"nodes": [], "edges": []'),                              # truncated json
]


@pytest.mark.parametrize(
    "idx, fmt, payload",
    [(i, f, p) for i, (f, p) in enumerate(MALFORMED_FIXTURES)],
)
def test_malformed_fail_closed_vs_bounded_recovery(idx, fmt, payload):
    """Assert Strict fails closed while Hardened performs bounded recovery with audit evidence."""
    # 1. Strict mode MUST fail closed (raise an exception)
    with pytest.raises(Exception) as exc_info:
        _read_by_fmt(fmt, payload, mode="strict")
    assert exc_info.value is not None, f"strict mode did not raise on malformed fixture {idx}"

    # 2. Hardened mode MUST perform bounded recovery and return a usable graph
    g_hardened = _read_by_fmt(fmt, payload, mode="hardened")
    assert g_hardened is not None, f"hardened mode returned None on fixture {idx}"
    assert g_hardened.mode == "hardened"

    # 3. Decision records ledger MUST record the recovery action
    records = g_hardened.decision_records()
    assert len(records) > 0, f"hardened mode left empty decision records on fixture {idx}"

    # Audit record structure check
    first_record = records[0]
    assert "operation" in first_record
    assert "action" in first_record
    assert "mode" in first_record
    assert "incompatibility_probability" in first_record
    assert first_record["mode"] == "hardened"

    # Also test top-level helper parity
    assert fnx.decision_records(g_hardened) == records

    # 4. Ledger drainability: draining empties the ledger
    drained = g_hardened.drain_decision_records()
    assert len(drained) == len(records)
    assert len(g_hardened.decision_records()) == 0
    assert len(fnx.decision_records(g_hardened)) == 0


# ===========================================================================
# 4. Planted Negative Test (Unknown Incompatible Features Fail Closed in Hardened Mode)
# ===========================================================================


def test_planted_negative_unknown_features_fail_closed_in_hardened_mode():
    """Security doctrine invariant: unknown incompatible features MUST fail closed even in Hardened mode."""
    planted_negative_json = """{
      "mode": "hardened",
      "nodes": ["0", "1"],
      "edges": [
        {"left": "0", "right": "1", "attrs": {"__fnx_incompatible_feature_test__": true}}
      ]
    }"""

    # In Strict mode: fail closed
    with pytest.raises(Exception):
        fnx.read_json_graph(io.StringIO(planted_negative_json), mode="strict")

    # In Hardened mode: MUST STILL FAIL CLOSED because unknown features cannot be safely bypassed
    with pytest.raises(Exception, match="incompatible edge metadata|failed closed"):
        fnx.read_json_graph(io.StringIO(planted_negative_json), mode="hardened")

    # Also via context manager
    with fnx.config(compatibility_mode="hardened"):
        with pytest.raises(Exception, match="incompatible edge metadata|failed closed"):
            fnx.read_json_graph(io.StringIO(planted_negative_json))

    with fnx.compatibility_mode("hardened"):
        with pytest.raises(Exception, match="incompatible edge metadata|failed closed"):
            fnx.read_json_graph(io.StringIO(planted_negative_json))
