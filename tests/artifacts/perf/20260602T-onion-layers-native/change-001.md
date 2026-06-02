# Change 001: Native `onion_layers` Wrapper Route

- Bead: `br-r37-c1-l5es6`
- Lever: route `fnx.onion_layers` to `_fnx.onion_layers_rust` after the existing native kernel parity fix, keeping NetworkX delegation only as a helper-unavailable fallback.
- Baseline, rch call benchmark: fallback mean `0.0632563438033685` seconds.
- After, rch call benchmark: native mean `0.004572276002727449` seconds.
- Delta: `13.83476057999012x` speedup, `92.7718300998548%` faster.
- Hyperfine process benchmark: `0.5400468921000001` seconds -> `0.3894861284200001` seconds, `1.3865625825771226x`, `27.87920195124849%` faster.
- Upstream NetworkX call benchmark: `0.005605684203328565` seconds.
- Golden digest: `93affbdb8954c6f7cd29b9623caa88ec8dcd0b2df108f1acf625deee8e9485af`, unchanged across fallback, native, and upstream.
- Score: Impact 5 x Confidence 5 / Effort 2 = 12.5. Keep.
