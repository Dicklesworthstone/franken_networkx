# Sparse Weighted Edge-Only Attr Sync

Bead: br-r37-c1-modhw
Pass: 62

## Profile-Backed Target

Workload: `to_scipy_weighted_float` on deterministic BA(8000, 4) with float `weight` attrs.

Baseline sweep:
- FNX mean: `0.03464299042908741s`
- NetworkX mean: `0.029742007426518415s`
- FNX / NetworkX: `1.1647831947684608`
- Digest: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`

Baseline cProfile over 12 calls:
- Total `_call_case`: `0.517s`
- Native `adjacency_default_order_arrays`: `0.287s`
- `_sync_rust_edge_attrs` / `_fnx_sync_attrs_to_inner`: `0.032s`

## Lever

Add `Graph._fnx_sync_edge_attrs_to_inner()` and call it only from weighted sparse native export. The full `_fnx_sync_attrs_to_inner()` path is unchanged for callers that need node attributes.

The lever comes from the graveyard hot-path/data-layout guidance: isolate the hot path from unrelated scans, keep sparse graph kernels on CSR/COO-style edge data, and avoid runtime fallback paths that degrade into linear scans.

## After

After sweep:
- FNX mean: `0.03367545385013467s`
- NetworkX mean: `0.03410225157443035s`
- FNX / NetworkX: `0.9874847640671419`
- Digest matched NetworkX: `true`

After confirm direct run:
- FNX mean: `0.030754169758874923s`
- FNX median: `0.02668839300167747s`
- Digest: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`

After cProfile over 12 calls:
- Total `_call_case`: `0.492s`
- Native `adjacency_default_order_arrays`: `0.297s`
- `_sync_rust_edge_attrs` / `_fnx_sync_attrs_to_inner`: no longer in top 40

Hyperfine process envelope:
- Baseline: `0.7900816847400001s +/- 0.023862350578784778s`
- After: `0.79841152096s +/- 0.017723767680848643s`
- Verdict: no process-level win; command is dominated by interpreter startup and graph construction.

## Score

Impact `2` x Confidence `4` / Effort `2` = `4.0`.

Kept because the profile-backed hot call improved, digest parity held, and the sync overhead was removed from the target profile. The process-level hyperfine non-win is recorded and keeps the impact score conservative.
