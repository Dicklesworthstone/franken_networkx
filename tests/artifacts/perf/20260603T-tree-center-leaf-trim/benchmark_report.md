# Benchmark Report: tree center leaf trimming

## Direct Samples
- FNX center baseline, repeat=50: `0.019387142599443904s`
- NetworkX center baseline, repeat=50: `0.001101763501064852s`
- FNX center after, repeat=50: `0.002302988637238741s`
- Direct self-speedup: `8.42x`
- Residual vs NetworkX after: `2.09x`

## Hyperfine
- Baseline: `683.4 ms +/- 40.7 ms`
- After: `359.7 ms +/- 19.7 ms`
- Process-envelope speedup: `1.90x`

## Profile Shift
- Baseline: `center` called `eccentricity`; native `_fnx.eccentricity` consumed `0.928s` over 50 calls.
- After: `center` uses `_tree_center_unweighted`; no native eccentricity call appears in the center path.

## All-Output Guard
- Baseline FNX all-output mean: `0.07614819670852739s`
- After FNX all-output mean: `0.05960408019891474s`
- All-output SHA stayed `ded31e37db96e807e690e4092edffee407a0ef980cf0ca7274dd4806ac8caf12`.

## Score
Impact 5 x Confidence 5 / Effort 2 = `12.5`. Keep.
