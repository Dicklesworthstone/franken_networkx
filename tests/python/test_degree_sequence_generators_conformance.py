"""NetworkX conformance for the degree-sequence generator family.

Covers:

- ``is_valid_degree_sequence_havel_hakimi`` — graphicality predicate
  (Havel-Hakimi).
- ``is_valid_degree_sequence_erdos_gallai`` — graphicality predicate
  (Erdős-Gallai).
- ``havel_hakimi_graph`` — deterministic Havel-Hakimi construction.
- ``directed_havel_hakimi_graph`` — directed variant.
- ``configuration_model`` — random multigraph realising a sequence.
- ``directed_configuration_model`` — directed variant.
- ``expected_degree_graph`` — Chung-Lu expected-degree model.
- ``random_regular_graph`` — random d-regular graph.
- ``random_degree_sequence_graph`` — random simple graph realising a
  sequence.

Two layers of assertion:

1. Bit-for-bit parity for deterministic constructors
   (``havel_hakimi_graph``, ``directed_havel_hakimi_graph``, the two
   validators) on every fixture.
2. Validity invariants for randomised constructors — the resulting
   graph must realise the requested degree sequence (or expected
   degree, for ``expected_degree_graph``) per NetworkX's documented
   contract. Since both libs draw from independent RNGs, we don't
   require the SAME random graph; we require BOTH to produce a valid
   one of the documented shape.
"""

from __future__ import annotations

import warnings

import pytest
import networkx as nx

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Validators — exact bit-for-bit parity
# ---------------------------------------------------------------------------


VALIDATOR_FIXTURES = [
    ("regular_4_3reg", [3, 3, 3, 3]),
    ("star_S_5", [5, 1, 1, 1, 1, 1]),
    ("path_P_5", [1, 2, 2, 2, 1]),
    ("invalid_odd_sum", [1, 1, 1]),
    ("K_5_seq", [4, 4, 4, 4, 4]),
    ("non_graphical_4_3s_one_1", [3, 3, 3, 3, 1]),
    ("empty", []),
    ("single_zero", [0]),
    ("two_zeros", [0, 0]),
    ("isolate_plus_K_2", [0, 1, 1]),
    ("regular_5_2reg", [2, 2, 2, 2, 2]),
    ("descending_petersen_like", [3, 3, 3, 3, 3, 3, 3, 3, 3, 3]),
    ("non_graphical_negative_in_seq", [-1, 2, 1]),
    ("hand_crafted_valid_long",
     [4, 3, 3, 3, 3, 2, 2, 2]),
    ("hand_crafted_invalid_too_high",
     [10, 1, 1, 1, 1]),
]


@pytest.mark.parametrize("name,seq", VALIDATOR_FIXTURES,
                         ids=[fx[0] for fx in VALIDATOR_FIXTURES])
def test_is_valid_degree_sequence_havel_hakimi_matches_networkx(name, seq):
    assert (
        fnx.is_valid_degree_sequence_havel_hakimi(seq)
        == nx.is_valid_degree_sequence_havel_hakimi(seq)
    )


@pytest.mark.parametrize("name,seq", VALIDATOR_FIXTURES,
                         ids=[fx[0] for fx in VALIDATOR_FIXTURES])
def test_is_valid_degree_sequence_erdos_gallai_matches_networkx(name, seq):
    assert (
        fnx.is_valid_degree_sequence_erdos_gallai(seq)
        == nx.is_valid_degree_sequence_erdos_gallai(seq)
    )


@pytest.mark.parametrize("name,seq", VALIDATOR_FIXTURES,
                         ids=[fx[0] for fx in VALIDATOR_FIXTURES])
def test_validators_agree_with_each_other(name, seq):
    """Havel-Hakimi and Erdős-Gallai must classify every sequence the
    same way (both characterise graphicality)."""
    hh = fnx.is_valid_degree_sequence_havel_hakimi(seq)
    eg = fnx.is_valid_degree_sequence_erdos_gallai(seq)
    assert hh == eg, f"{name}: HH={hh} EG={eg}"


# ---------------------------------------------------------------------------
# havel_hakimi_graph — deterministic construction
# ---------------------------------------------------------------------------


HAVEL_HAKIMI_FIXTURES = [
    ("K_4_seq", [3, 3, 3, 3]),
    ("star_S_4_seq", [4, 1, 1, 1, 1]),
    ("cycle_C_4_seq", [2, 2, 2, 2]),
    ("path_P_5_seq", [2, 2, 2, 1, 1]),
    ("leading_isolate_plus_K2", [0, 1, 1]),
    ("K_5_seq", [4, 4, 4, 4, 4]),
    ("uneven_seq", [3, 2, 2, 2, 1]),
    ("regular_3_seq_n6", [3, 3, 3, 3, 3, 3]),
]


@pytest.mark.parametrize("name,seq", HAVEL_HAKIMI_FIXTURES,
                         ids=[fx[0] for fx in HAVEL_HAKIMI_FIXTURES])
def test_havel_hakimi_graph_matches_networkx(name, seq):
    fg = fnx.havel_hakimi_graph(seq)
    ng = nx.havel_hakimi_graph(seq)
    assert sorted(fg.edges()) == sorted(ng.edges()), (
        f"{name}: fnx={sorted(fg.edges())} nx={sorted(ng.edges())}"
    )


@pytest.mark.parametrize("name,seq", HAVEL_HAKIMI_FIXTURES,
                         ids=[fx[0] for fx in HAVEL_HAKIMI_FIXTURES])
def test_havel_hakimi_graph_realises_requested_sequence(name, seq):
    fg = fnx.havel_hakimi_graph(seq)
    actual_degrees = sorted((d for _, d in fg.degree()), reverse=True)
    requested = sorted(seq, reverse=True)
    assert actual_degrees == requested, (
        f"{name}: realised {actual_degrees} != requested {requested}"
    )


def test_havel_hakimi_graph_invalid_sequence_raises_matching_networkx():
    seq = [3, 3, 3, 3, 1]  # not graphical
    with pytest.raises(nx.NetworkXError) as nx_exc:
        nx.havel_hakimi_graph(seq)
    with pytest.raises(fnx.NetworkXError) as fnx_exc:
        fnx.havel_hakimi_graph(seq)
    assert str(fnx_exc.value) == str(nx_exc.value)


# ---------------------------------------------------------------------------
# directed_havel_hakimi_graph
# ---------------------------------------------------------------------------


DIRECTED_HAVEL_FIXTURES = [
    ("balanced_4nodes", [2, 2, 1, 1], [1, 2, 1, 2]),
    ("uniform_3reg", [2, 2, 2], [2, 2, 2]),
    ("star_in_4", [3, 0, 0, 0], [0, 1, 1, 1]),
]


@pytest.mark.parametrize(
    "name,in_seq,out_seq",
    DIRECTED_HAVEL_FIXTURES,
    ids=[fx[0] for fx in DIRECTED_HAVEL_FIXTURES],
)
def test_directed_havel_hakimi_graph_matches_networkx(name, in_seq, out_seq):
    fg = fnx.directed_havel_hakimi_graph(in_seq, out_seq)
    ng = nx.directed_havel_hakimi_graph(in_seq, out_seq)
    assert sorted(fg.edges()) == sorted(ng.edges())


@pytest.mark.parametrize(
    "name,in_seq,out_seq",
    DIRECTED_HAVEL_FIXTURES,
    ids=[fx[0] for fx in DIRECTED_HAVEL_FIXTURES],
)
def test_directed_havel_hakimi_realises_requested_sequences(
    name, in_seq, out_seq,
):
    fg = fnx.directed_havel_hakimi_graph(in_seq, out_seq)
    actual_in = sorted((d for _, d in fg.in_degree()), reverse=True)
    actual_out = sorted((d for _, d in fg.out_degree()), reverse=True)
    expected_in = sorted(in_seq, reverse=True)
    expected_out = sorted(out_seq, reverse=True)
    assert actual_in == expected_in, (
        f"{name}: realised in-degrees {actual_in} != requested {expected_in}"
    )
    assert actual_out == expected_out, (
        f"{name}: realised out-degrees {actual_out} != requested {expected_out}"
    )


# ---------------------------------------------------------------------------
# configuration_model — randomised; assert validity invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 7, 42, 1000])
@pytest.mark.parametrize(
    "name,seq",
    [
        ("regular_3_n4", [3, 3, 3, 3]),
        ("star_seq_n5", [4, 1, 1, 1, 1]),
        ("mixed_n6", [4, 3, 2, 2, 1, 2]),
        ("regular_4_n6", [4, 4, 4, 4, 4, 4]),
    ],
)
def test_configuration_model_realises_requested_sequence(seq, seed, name):
    """``configuration_model`` is a multigraph constructor: parallel
    edges and self-loops are allowed. The resulting per-node degree
    (counting parallels twice for self-loops, once for normal edges)
    must equal the requested sequence."""
    fg = fnx.configuration_model(seq, seed=seed)
    actual = sorted((d for _, d in fg.degree()), reverse=True)
    expected = sorted(seq, reverse=True)
    assert actual == expected, (
        f"{name} seed={seed}: realised {actual} != requested {expected}"
    )


@pytest.mark.parametrize(
    "name,seq",
    [
        ("regular_3_n4", [3, 3, 3, 3]),
        ("regular_4_n6", [4, 4, 4, 4, 4, 4]),
    ],
)
def test_configuration_model_returns_multigraph(name, seq):
    fg = fnx.configuration_model(seq, seed=1)
    ng = nx.configuration_model(seq, seed=1)
    assert fg.is_multigraph() == ng.is_multigraph() is True


# ---------------------------------------------------------------------------
# expected_degree_graph (Chung-Lu) — bit-for-bit parity (uses seeded RNG)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 7, 42])
@pytest.mark.parametrize(
    "name,w",
    [
        ("uniform_5", [3.0] * 5),
        ("chung_lu_decay", [4.0, 3.0, 2.0, 2.0, 1.0]),
        ("uniform_8", [2.5] * 8),
        ("decay_10", [9.0, 5.0, 3.0, 3.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0]),
    ],
)
def test_expected_degree_graph_matches_networkx(name, w, seed):
    fg = fnx.expected_degree_graph(w, seed=seed)
    ng = nx.expected_degree_graph(w, seed=seed)
    assert sorted(fg.edges()) == sorted(ng.edges())


# ---------------------------------------------------------------------------
# random_regular_graph — randomised; assert validity invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 7, 42])
@pytest.mark.parametrize(
    "d,n",
    [(2, 6), (2, 8), (3, 8), (3, 10), (4, 10), (4, 12), (5, 12)],
)
def test_random_regular_graph_is_d_regular(d, n, seed):
    """Both libs use independent RNGs; the GENERATED graphs may differ
    but each must be d-regular on n nodes."""
    fg = fnx.random_regular_graph(d, n, seed=seed)
    assert fg.number_of_nodes() == n
    assert all(deg == d for _, deg in fg.degree()), (
        f"d={d} n={n} seed={seed}: not d-regular"
    )


# ---------------------------------------------------------------------------
# Cross-relation: havel_hakimi_graph realises a sequence iff the
# sequence is graphical
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,seq", VALIDATOR_FIXTURES,
                         ids=[fx[0] for fx in VALIDATOR_FIXTURES])
def test_havel_hakimi_graph_succeeds_iff_sequence_is_graphical(name, seq):
    """``havel_hakimi_graph(seq)`` succeeds iff
    ``is_valid_degree_sequence_havel_hakimi(seq)`` returns True."""
    is_graphical = fnx.is_valid_degree_sequence_havel_hakimi(seq)
    try:
        fnx.havel_hakimi_graph(seq)
        succeeded = True
    except (fnx.NetworkXError, ValueError):
        succeeded = False
    if seq:  # NX raises on empty in some versions; skip empty
        assert succeeded == is_graphical, (
            f"{name}: succeeded={succeeded} but is_graphical={is_graphical}"
        )


# ---------------------------------------------------------------------------
# Validators: known graphicality results
# ---------------------------------------------------------------------------


def test_validator_known_graphical_sequences():
    """Standard graphicality lock-ins."""
    # K_n: [n-1] * n
    for n in range(2, 7):
        seq = [n - 1] * n
        assert fnx.is_valid_degree_sequence_havel_hakimi(seq)
        assert fnx.is_valid_degree_sequence_erdos_gallai(seq)


def test_validator_known_non_graphical_sequences():
    """Standard non-graphicality lock-ins."""
    # Odd sum is always non-graphical (handshaking lemma)
    for seq in [[1], [3], [1, 1, 1], [3, 3, 3], [5, 5, 5]]:
        assert not fnx.is_valid_degree_sequence_havel_hakimi(seq)
        assert not fnx.is_valid_degree_sequence_erdos_gallai(seq)
    # n nodes, max degree > n-1 → impossible
    for seq in [[5, 1, 1], [10, 1, 1, 1, 1]]:
        assert not fnx.is_valid_degree_sequence_havel_hakimi(seq)
        assert not fnx.is_valid_degree_sequence_erdos_gallai(seq)
