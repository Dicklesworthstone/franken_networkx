"""br-r37-c1-2vmel: read_edgelist / read_weighted_edgelist native fast-path
parity vs networkx.

The default-kwargs paths route through the Rust ``read_edgelist_simple``
single-pass parser (modes data_true / data_false / weight_float). These
tests pin the line semantics (skip <2-token lines, comment strip),
delegation gates (extra tokens, underscore floats, non-default kwargs),
float parity (inf/nan/exp), duplicate-edge overwrite, and error parity.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _canon(g):
    # repr-based so NaN weights compare equal (nan != nan as objects).
    return (
        repr([(n, dict(a)) for n, a in g.nodes(data=True)]),
        repr([(u, v, dict(d)) for u, v, d in g.edges(data=True)]),
        repr({n: list(g[n]) for n in g}),
    )


def _write(tmp_path, content, name="g.el"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_fast_path_engaged(tmp_path):
    p = _write(tmp_path, "a b\nb c\n")
    native = fnx._fnx.read_edgelist_simple(p, "data_true")
    assert native is not None
    assert _canon(fnx.read_edgelist(p)) == _canon(native)


def test_nodata_corpus_matches_nx(tmp_path):
    rnd = random.Random(20260605)
    for trial in range(15):
        n = rnd.choice([0, 1, 2, 40, 200])
        g = nx.Graph()
        labels = [rnd.choice([str(i), f"n_{i}", f"ü{i}"]) for i in range(n)]
        g.add_nodes_from(labels)
        for _ in range(n * 2):
            g.add_edge(rnd.choice(labels), rnd.choice(labels))
        p = _write(tmp_path, "", name=f"c{trial}.el")
        nx.write_edgelist(g, p, data=False)
        assert _canon(fnx.read_edgelist(p)) == _canon(nx.read_edgelist(p)), trial


def test_weighted_corpus_matches_nx(tmp_path):
    rnd = random.Random(7)
    for trial in range(10):
        g = nx.Graph()
        for _ in range(80):
            g.add_edge(
                str(rnd.randrange(40)),
                str(rnd.randrange(40)),
                weight=round(rnd.uniform(-50, 50), 6),
            )
        p = _write(tmp_path, "", name=f"w{trial}.el")
        nx.write_weighted_edgelist(g, p)
        assert _canon(fnx.read_weighted_edgelist(p)) == _canon(
            nx.read_weighted_edgelist(p)
        ), trial


@pytest.mark.parametrize(
    "content,kwargs",
    [
        ("a b\n\nc d\n", {}),  # blank lines skipped
        ("a b\nlonely\nc d\n", {}),  # 1-token lines skipped
        ("# hdr\na b # tail\nc d#tight\n", {}),  # comments
        ("a\tb\nc\td\n", {}),  # tabs
        ("a b\nb a\na b\n", {}),  # duplicate edges
        ("a a\nb b\n", {}),  # self-loops
        ("a b\r\nc d\r\n", {}),  # CRLF
        ("a b\nc d", {}),  # no trailing newline
        ("a b junk extra\nc d x\n", {"data": False}),  # extras ignored
    ],
)
def test_handcrafted_files_match_nx(tmp_path, content, kwargs):
    p = _write(tmp_path, content)
    assert _canon(fnx.read_edgelist(p, **kwargs)) == _canon(
        nx.read_edgelist(p, **kwargs)
    )


@pytest.mark.parametrize(
    "content",
    [
        "a b 1.5\nc d 2\n",  # basic
        "a b\nc d 2\n",  # missing weight column -> {}
        "a b 1e-3\nc d -2.5E2\ne f +4.25\n",  # exponents/signs
        "a b inf\nc d nan\ne f -Infinity\ng h NAN\n",  # special floats
        "a b 1_0\nc d 2\n",  # underscore: kernel delegates, result still matches
        "a b 1\na b 2.5\n",  # duplicate overwrites
        "a b -0.0\n",  # negative zero
        "a b 1e308\nc d 1e309\n",  # overflow -> inf
    ],
)
def test_weighted_handcrafted_match_nx(tmp_path, content):
    p = _write(tmp_path, content)
    a = _canon(nx.read_weighted_edgelist(p))
    b = _canon(fnx.read_weighted_edgelist(p))
    assert a == b


@pytest.mark.parametrize(
    "content",
    [
        "a b 1.5 9\n",  # length mismatch -> IndexError
        "a b xyz\n",  # bad float -> TypeError
    ],
)
def test_weighted_error_parity(tmp_path, content):
    p = _write(tmp_path, content)
    with pytest.raises(Exception) as nx_err:
        nx.read_weighted_edgelist(p)
    with pytest.raises(Exception) as fnx_err:
        fnx.read_weighted_edgelist(p)
    assert type(fnx_err.value) is type(nx_err.value)
    assert str(fnx_err.value) == str(nx_err.value)


def test_data_true_with_dict_columns_delegates(tmp_path):
    g = nx.Graph()
    g.add_edge("a", "b", weight=2, color="red")
    g.add_edge("b", "c")
    p = _write(tmp_path, "")
    nx.write_edgelist(g, p)
    assert _canon(fnx.read_edgelist(p)) == _canon(nx.read_edgelist(p))


def test_non_default_kwargs_still_delegate(tmp_path):
    p = _write(tmp_path, "1 2\n2 3\n")
    assert list(fnx.read_edgelist(p, nodetype=int)) == [1, 2, 3]
    assert fnx.read_edgelist(p, create_using=fnx.DiGraph).is_directed()
    g_cu = fnx.read_edgelist(p, create_using=fnx.Graph)
    assert type(g_cu) is fnx.Graph


def test_fast_path_graph_mutable_and_kernel_exact(tmp_path):
    p = _write(tmp_path, "a b 1.5\nb c 2\n")
    g = fnx.read_weighted_edgelist(p)
    g["a"]["b"]["weight"] = 7
    assert g["b"]["a"]["weight"] == 7
    g.add_edge("c", "z")
    gn = nx.Graph([("a", "b", {"weight": 7}), ("b", "c", {"weight": 2.0}), ("c", "z", {})])
    assert dict(fnx.single_source_dijkstra_path_length(g, "a")) == dict(
        nx.single_source_dijkstra_path_length(gn, "a")
    )
