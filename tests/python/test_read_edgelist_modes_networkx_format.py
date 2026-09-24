"""Mode-aware read_edgelist must read NetworkX's edge-list format.

br-r37-c1-rc0923-epic-silent-wrong-answers-nro4w.3: with ``mode="hardened"`` (or
the global hardened config) read_edgelist handed the file to the Rust engine's
own ``left right k=v`` parser, which treats NetworkX dict-literal lines — exactly
what ``write_edgelist`` writes — as malformed: hardened "recovered" every line
away and returned an EMPTY graph, and explicit strict raised. These tests pin:
round-trips in every mode, bounded per-line recovery with an audit record in
hardened, fail-closed strict, and the native ``k=v`` token still accepted.
"""

from __future__ import annotations

import io

import networkx as nx
import pytest

import franken_networkx as fnx


def _weighted_graph(module, cls="Graph"):
    G = getattr(module, cls)()
    G.add_edge("a", "b", weight=1, color="red")
    G.add_edge("b", "c", weight=2.5)
    G.add_edge("c", "a")
    return G


def _rows(G):
    return sorted((str(u), str(v), sorted(d.items())) for u, v, d in G.edges(data=True))


@pytest.mark.parametrize("mode", [None, "strict", "hardened"])
@pytest.mark.parametrize("cls", ["Graph", "DiGraph"])
def test_write_then_read_round_trips_in_every_mode(tmp_path, mode, cls):
    path = tmp_path / "g.edgelist"
    fnx.write_edgelist(_weighted_graph(fnx, cls), path)
    create_using = getattr(fnx, cls)
    kwargs = {} if mode is None else {"mode": mode}
    H = fnx.read_edgelist(path, create_using=create_using, **kwargs)
    ref = nx.read_edgelist(path, create_using=getattr(nx, cls))
    assert _rows(H) == _rows(ref)
    assert list(H.nodes()) == [str(n) for n in ref.nodes()]
    if mode is not None:
        assert H.mode == mode
        assert all(r["action"] == "allow" for r in H.decision_records())


@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_mode_path_honours_nx_keywords(tmp_path, mode):
    path = tmp_path / "typed.csv"
    path.write_text("1,2,3.5\n2,3,7\n")
    kwargs = {"delimiter": ",", "nodetype": int, "data": [("weight", float)]}
    H = fnx.read_edgelist(path, mode=mode, **kwargs)
    ref = nx.read_edgelist(path, **kwargs)
    assert list(H.edges(data=True)) == list(ref.edges(data=True))
    assert all(isinstance(n, int) for n in H)


def test_global_hardened_config_reads_networkx_format(tmp_path):
    path = tmp_path / "g.edgelist"
    fnx.write_edgelist(_weighted_graph(fnx), path)
    old = fnx.get_compatibility_mode()
    try:
        fnx.config.compatibility_mode = "hardened"
        H = fnx.read_edgelist(path)
    finally:
        fnx.set_compatibility_mode(old)
    assert H.number_of_edges() == 3
    assert H.mode == "hardened"


def test_hardened_skips_only_malformed_lines_and_records_each():
    payload = (
        "a b {'weight': 1}\n"
        "lonely\n"  # < 2 fields: nx silently skips; hardened records the skip
        "b c {'weight': 2}\n"
        "c d {not a dict\n"  # nx raises TypeError on this line
        "d e\n"
    )
    H = fnx.read_edgelist(io.StringIO(payload), mode="hardened")
    assert _rows(H) == [("a", "b", [("weight", 1)]), ("b", "c", [("weight", 2)]), ("d", "e", [])]
    recoveries = [r for r in H.decision_records() if r["action"] == "full_validate"]
    assert len(recoveries) == 2
    assert all(r["mode"] == "hardened" and r["operation"] == "read_edgelist" for r in recoveries)
    assert "line 2" in recoveries[0]["rationale"] and "line 4" in recoveries[1]["rationale"]


def test_strict_fails_closed_on_malformed_lines():
    with pytest.raises(TypeError, match="Failed to convert edge data"):
        fnx.read_edgelist(io.StringIO("a b {oops\n"), mode="strict")
    with pytest.raises(OSError, match="failed closed: line 2 malformed"):
        fnx.read_edgelist(io.StringIO("a b\nlonely\n"), mode="strict")


@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_native_attribute_token_still_accepted(mode):
    H = fnx.read_edgelist(io.StringIO("0 1 weight=2.5\n1 2 weight=4.0\n"), mode=mode)
    assert _rows(H) == [("0", "1", [("weight", 2.5)]), ("1", "2", [("weight", 4.0)])]
