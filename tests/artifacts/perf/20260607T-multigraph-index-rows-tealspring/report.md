# MultiGraph Index-Row Flip Rejection

- Bead: `br-r37-c1-d58s8`
- Agent: `TealSpring`
- Date: `2026-06-07`
- Lever: replace `MultiGraph` neighbor rows with index-keyed rows while keeping the existing edge bucket table.
- Verdict: rejected, source restored, Score `0.0`.

## Profile-Backed Target

The target came from the current substrate perf bead plus the focused profile in this bundle. Baseline `cProfile` showed `MultiGraph` construction and add-loop cost dominated by the native constructor/add-edge surface:

- Baseline total: `4.443s`
- `build_ctor`: `3.471s`
- `MultiGraph.add_edge`: `0.834s`

The structural hypothesis was that integer-keyed neighbor rows would remove string row lookup tax from `MultiGraph` constructors and mutators.

## Behavior Proof

Golden behavior was unchanged during the candidate and after restoration:

- `baseline_proof.json`: `golden_sha256 = c155b298352ea6d0a9ba845fc16e270d88c91f460fb3d35f2069d477fcffc45c`
- `after_proof.json`: `golden_sha256 = c155b298352ea6d0a9ba845fc16e270d88c91f460fb3d35f2069d477fcffc45c`
- `restored_proof.json`: `golden_sha256 = c155b298352ea6d0a9ba845fc16e270d88c91f460fb3d35f2069d477fcffc45c`
- Core proof: `matches_nx = true`
- Tracked numeric/bool display-conflict surface: `display_conflict_matches_nx = false` before, during, and after; this records the existing current behavior and was not changed by the lever.

Isomorphism surface covered node order, neighbor order, edge key order, graph attrs, edge attrs, duplicate key update semantics, self-loops, copy, pickle round-trip, and removal behavior. No floating-point algorithm output was introduced. RNG inputs were explicitly seeded in the benchmark fixture.

## Benchmark Gate

Same-run direct timing regressed for the FNX scenarios:

| Scenario | Baseline FNX mean | Candidate FNX mean | Speedup |
|---|---:|---:|---:|
| ctor plain | `0.088078s` | `0.160796s` | `0.55x` |
| ctor keyed | `0.081989s` | `0.138605s` | `0.59x` |
| ctor attr | `0.084107s` | `0.085834s` | `0.98x` |
| add_loop plain | `0.088499s` | `0.142900s` | `0.62x` |
| add_loop keyed | `0.060126s` | `0.095634s` | `0.63x` |
| add_loop attr | `0.083237s` | `0.160990s` | `0.52x` |

Hyperfine also failed the keep gate:

| Scenario | Baseline mean | Candidate mean | Speedup |
|---|---:|---:|---:|
| ctor plain | `1.754690s` | `1.911360s` | `0.92x` |
| ctor keyed | `1.412746s` | `2.131239s` | `0.66x` |
| ctor attr | `0.912515s` | `0.972477s` | `0.94x` |
| add_loop keyed | `0.996492s` | `1.090595s` | `0.91x` |

Candidate profile worsened:

- Candidate total: `6.653s`
- `build_ctor`: `5.213s`
- `MultiGraph.add_edge`: `1.200s`

The restored run returned to the baseline behavior hash and a noisy baseline timing envelope.

## Diagnosis

The index-row flip did not remove enough work. It added endpoint-index lookup and row repair cost while the canonical edge bucket table still performed string-pair storage and lookup. That made the lever a partial representation split rather than a complete construction primitive.

## Next Primitive

Do not repeat the naive row flip. The next profile-backed target should be a batch-local `MultiGraph`/`MultiDiGraph` constructor kernel: intern endpoints once per batch, prepare canonical endpoint indices and edge keys in one pass, and commit rows plus edge buckets without per-edge node probes. Target ratio: keyed `MultiGraph` constructor `<=1.50x` vs NetworkX or at least `1.25x` same-worker speedup over the current FNX baseline.
