#!/bin/bash
# Run the adjacency-read probe once per arm, STRICTLY SEQUENTIALLY.
#
# Sequential is not tidiness: two timing loops on the same cores silently
# corrupt both, and the arms are compared by their ratios against a networkx
# control that is re-measured inside each run.
set -euo pipefail

W=/data/tmp/claude-1000/-data-projects-franken-networkx/58e12b6f-96f8-4c7b-b881-51d9992f6f6f/scratchpad
PY=/data/projects/franken_networkx/.venv/bin/python

for arm in before after; do
    farm="$W/farm_$arm"
    bash "$W/make_farm.sh" "$farm" "$W/$arm.whl"
done

echo "=== ELF identity of the two arms ==="
sha256sum "$W/farm_before/franken_networkx/_fnx.abi3.so" \
          "$W/farm_after/franken_networkx/_fnx.abi3.so"
if cmp -s "$W/farm_before/franken_networkx/_fnx.abi3.so" \
          "$W/farm_after/franken_networkx/_fnx.abi3.so"; then
    echo "FATAL: the two arms are the same binary -- nothing to compare" >&2
    exit 1
fi

for arm in before after; do
    farm="$W/farm_$arm"
    so="$farm/franken_networkx/_fnx.abi3.so"

    echo ""
    echo "################ PARITY: $arm ################"
    # Non-fatal: a divergence present on BOTH arms is pre-existing, not this
    # change. Comparing the two parity runs is the discriminator.
    PYTHONPATH="$farm" "$PY" "$W/parity_intkeys.py" 2>&1 | tee "$W/parity_$arm.log" || true

    echo ""
    echo "################ VIEW-PARITY SUITE: $arm ################"
    # The regression tests that shipped with the change under test. These are
    # expected to FAIL on the before arm and PASS on the after arm -- a guard
    # that passes on the unfixed arm is not guarding anything.
    PYTHONPATH="$farm" "$PY" -m pytest -q \
        /data/projects/franken_networkx/tests/python/test_view_descriptor_parity.py \
        2>&1 | tail -6 | tee "$W/pytest_$arm.log" || true

    echo ""
    echo "################ TIMING: $arm ################"
    PYTHONPATH="$farm" FNX_ARM="$arm" FNX_EXPECT_SO="$so" \
        "$PY" "$W/probe_arms.py" 2>&1 | tee "$W/arm_$arm.log" | grep -vE '^\{'
done
