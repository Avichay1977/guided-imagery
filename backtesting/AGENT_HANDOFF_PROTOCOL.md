# Agent Handoff Protocol — RelativeStrengthRotation_v1

Every implementing agent (A2) must return exactly the following after each
gate step. Gatekeeper (A1) will not accept incomplete handoffs.

---

## Required Return Format (A2 → A1/A0)

```
1. files created/modified:
   <list of file paths, one per line>

2. command run:
   <exact command, including all test file paths and flags>

3. raw stdout:
   <paste the full pytest terminal output, including dot progress and summary line>

4. raw stderr:
   <paste verbatim, or "(empty)" if nothing was printed to stderr>

5. exit code:
   <integer, must be 0 for PASS>

6. commit hash (if committed):
   <short hash, e.g. 4acd94f>

7. confirmation of forbidden actions not taken:
   - No backtests run: YES / NO
   - No market data used: YES / NO
   - No strategy_lab_runner executed: YES / NO
   - No LIVE-GO emitted: YES / NO
   - No RESEARCH-GO emitted: YES / NO
   - No prior NO-GO verdict modified: YES / NO
```

---

## Gatekeeper Rules (A1)

**No raw stdout = no pass.**
A gate cannot be passed based on a summary ("38 tests passed") without the
raw pytest terminal output showing the dot progress line and summary.

**No exit code = no pass (unless raw stdout conclusively shows pytest passed
AND prior context confirms the exact command was run).**
When in doubt, re-run the command and return both stdout and the exit code.

**Exit code ≠ 0 = fail.**
A non-zero exit code is a gate failure even if some tests passed (the failing
tests must be investigated and fixed before re-submission).

**`unittest` is not a substitute for `pytest`.**
Running `python -m unittest discover` instead of `python -m pytest` produces
incompatible output and is not accepted as gate evidence.

**Screenshots are not gate evidence.**
Terminal screenshots, copy-pasted logs from a different session, or output
from a different machine/branch are not accepted as evidence for this gate.

**Dummy tests are a protocol violation.**
A test that always passes regardless of implementation (e.g., `assert True`)
is a dummy test and invalidates the gate submission.

**p75 must never be used as p95.**
Any module that computes `np.percentile(sims, 75)` and calls it `p95_*` is a
spec violation. The gatekeeper will reject the gate and require a fix.

**v1.2 is only diagnostic.**
No v1.2 output may produce or imply a RESEARCH-GO or LIVE-GO verdict.
The `v1_2_diagnostic_label` must be `PORTFOLIO_DIAGNOSTIC_ONLY`.

**B2 is report-only.**
B2 results must not affect the v1.1 verdict. `v1_1_verdict_impact` must
equal `"NONE"`. Weakening B1 to favor the strategy is a spec violation.

**No prior NO-GO verdict can be converted.**
BreakoutVolumeConfluence_v1, TrendPullbackConfluence_v1, and
MomentumContinuationConfluence_v1 remain NO-GO. No code change may alter
their recorded verdicts.

---

## Next Required Command (as of current state)

After comparator p95 gate passed, the next gate command will be:

```
python -m pytest tests/test_rotation_backtester_run_engine.py \
  tests/test_rotation_random_selection_comparator.py \
  tests/test_rotation_benchmark_b2.py \
  tests/test_rotation_feature_matrix_builder.py \
  tests/test_rotation_backtester_scaffold.py \
  tests/test_relative_strength_rotation_v1_scaffold.py \
  tests/test_relative_strength_rotation_v1_spec.py \
  -q
```

*(File name `test_rotation_backtester_run_engine.py` is provisional; the exact
name will be specified in the Step 6 payload.)*

The current state command (all passing, 310 tests) is:

```
python -m pytest \
  tests/test_rotation_random_selection_comparator.py \
  tests/test_rotation_benchmark_b2.py \
  tests/test_rotation_feature_matrix_builder.py \
  tests/test_rotation_backtester_scaffold.py \
  tests/test_relative_strength_rotation_v1_scaffold.py \
  tests/test_relative_strength_rotation_v1_spec.py \
  -q
```

---

## Escalation Rules

If any of the following occur, A2 must stop and escalate to A0 via A1:

1. A test suite produces a result that contradicts a prior gate passage.
2. A commit would modify an existing CSV file or NO-GO verdict record.
3. Any module attempts to import `yfinance` or `fetch_yfinance_data` outside
   an explicitly authorized research gate.
4. Any module emits or computes a RESEARCH-GO or LIVE-GO token.
5. Any parameter in `RESEARCH_SPEC_RELATIVE_STRENGTH_ROTATION_V1.md` §5,
   §8, §10, §11, §12, or §13 would be changed by the proposed code.
6. A push is attempted to any branch other than
   `claude/backtester-nan-validation-loader-2lssL` without explicit A0 authorization.

---

*This protocol is the handoff contract.*
*It cannot be updated without a note in the next gate summary and a commit
to this file on the designated branch.*
