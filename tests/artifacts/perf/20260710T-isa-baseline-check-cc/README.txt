ISA baseline check, 2026-07-10 cc
Build emits: x86-64 baseline (fxsr/sse/sse2/x87), NO popcnt/avx2 — no .cargo/config, no target-cpu anywhere.
CROSS-WORKER, INCONCLUSIVE on magnitude:
  baseline closeness/complete/100 = 39.734us on vmi1227854
  native   closeness/complete/100 = 48.351us on hz1
different workers => no valid ratio (two-invocation rule). RUSTFLAGS=-C target-cpu=native DID forward + compile.
My bit-parallel kernels defer popcount off the O(|E|) loop, so limited direct upside; real leverage = dense-linalg (br-r37-c1-2zn1u).
