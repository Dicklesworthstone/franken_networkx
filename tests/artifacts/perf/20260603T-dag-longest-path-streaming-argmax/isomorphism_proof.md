# Isomorphism Proof

## Stable Tie-Break

The previous code built `us` in predecessor insertion order and used `max(us, key=lambda x: x[0])`. Python `max` starts with the first candidate and replaces it only when a later key is strictly greater.

The new loop initializes `maxu` from the first predecessor and updates only on `candidate_len > best_len`. Equal candidates keep the first predecessor, so NetworkX's tie-break is preserved.

## NaN And Comparison Errors

For `NaN`, `candidate_len > best_len` is false, matching Python `max` behavior after the initial candidate is selected. For incomparable values, the same Python `>` comparison is what raises `TypeError` in `max`; the new loop raises on the same comparison point.

## Negative Reset And Numeric Types

The new loop leaves `dist[v] = maxu if maxu[0] >= 0 else (0, v)` unchanged. All arithmetic remains Python addition of the same `dist[u][0]` and edge-weight objects from `_native_in_edges_data_key`, so integer, float, bool, `inf`, `NaN`, and mixed numeric exposure is unchanged.

## Golden Output

The output payload includes the longest path and node runtime types. SHA256 is identical across baseline FNX, NetworkX oracle, and after FNX:

`76214d0b33d25b721eb1437d081b03fcf320e749ed72ceb521a87215d5ebbb7f`

