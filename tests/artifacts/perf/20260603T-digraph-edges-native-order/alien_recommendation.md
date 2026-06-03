# Alien Primitive

Bead: `br-r37-c1-acuub`

Harvested principle: boundary-cost minimization and cache-friendly native materialization.

Source lookup:

- `/data/projects/alien_cs_graveyard/high_level_summary_of_frankensuite_planned_and_implemented_features_and_concepts.md` mentions the Transparent Safety Membrane pattern at an ABI boundary and staged fast paths.
- `/data/projects/alien_cs_graveyard/high_level_summary_of_frankensuite_planned_and_implemented_features_and_concepts.md` also calls out cache-sized/vectorized execution and the rule that constants dominate when asymptotics are equal.

Applied artifact:

Move the high-volume no-data edge projection out of Python's adjacency-view chain and into a safe Rust helper that emits the same ordered list of Python endpoint tuples. This removes repeated Python boundary crossings for adjacency and iterator wrappers while preserving the public view contract.

No unsafe code, C BLAS, LAPACK, MKL, or XLA was introduced.
