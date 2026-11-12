# Rejected Lever: Trusted Fresh-Edge Inner Insertion

Bead: `br-r37-c1-04z53.48`

## Target

Post-`bc260e51e` profiles still put most construction time in
`PyMultiGraph._fast_add_explicit_{int,str}_edge`:

- `multigraph_int_keys`: 450000 calls, 1.459s in the native fast method.
- `multigraph_str_keys`: 450000 calls, 1.515s in the native fast method.

## Lever Tried

Add a trusted `fnx-classes::MultiGraph` insertion path for fresh endpoint pairs
after the Python fast path has already checked that no edge bucket exists. The
candidate passed caller-provided node-presence facts to avoid duplicate inner
edge/node probes.

## Result

Golden digests still matched, but the measured win was too small for the keep
bar:

- Hyperfine `multigraph_int_keys`: 1.273792742s -> 1.229638668s, 1.04x.
- Hyperfine `multigraph_str_keys`: 1.316159398s -> 1.271075128s, 1.04x.
- Direct sweep `multigraph_int_keys`: 0.250299420s -> 0.245142800s, 1.02x.
- Direct sweep `multigraph_str_keys`: 0.244370248s -> 0.218703106s, 1.12x.

Score: `Impact 1.04 x Confidence 0.7 / Effort 1.0 = 0.73`.

Decision: rejected. Source was restored and the release extension rebuilt from
the restored source.

## Next Primitive

Do not repeat duplicate-probe micro-levers in this path. The next construction
attack should be the deeper integer-node substrate named by the prior range-node
report: compact contiguous integer node IDs / interned canonical storage behind
the Python-visible maps, with explicit proofs for first-object identity,
hash-equal collapse, node/edge order, and attr dict identity.
