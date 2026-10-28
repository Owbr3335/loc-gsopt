# Upstream adoption — October 27, 2026

## Baselines and preservation

Current upstream: `2d1411ab9b479e6a7cc76597a390943d4e0c5956` (October 25).
Both Grace's and Stanford's repositories pointed to this commit when reviewed.
The checkout was fast-forwarded, retaining the full author commit history.
Upstream source, config, LICENSE, CITATION.cff and uv.lock remain unchanged.

Previous upstream: `249f5315ae056653ef3e981cee6f2d60816e96ce`, retained on local
branch `baseline/april-2025`. The adopted commit is also marked by local branch
`baseline/october-2026`. Recovery copies are in
`../baseline-archives/2026-10-27/`: a Git bundle and a tar archive of all local
extensions, country data and saved runs. Old `local_runs/upstream_example` and
`local_runs/design` results remain historical and are not regenerated in place.

No GitHub fork was created and nothing was pushed. `origin` remains Stanford.
Our additions are maintained locally on top of the preserved upstream history.

## What changed in our integration

- `src/network_design/upstream.py` now consumes Brahe 1.x propagators and access
  windows, using the authors' `compute_contact_times`. Satellites receive stable
  per-provider indices for scheduling conflicts, including across ground sites.
- `local_tools/run_upstream.py` now invokes the actual upstream SCORE entry point
  with W&B and downloads disabled. Its default is one placement pass and one
  refinement pass, two Capella satellites, one day, one station.
- `check_design_upstream.py` and `check_schedule.py` compare our adapter/HiGHS
  scheduler with upstream access/CBC and run our country-constrained optimizer.
- RF integration uses `numpy.trapezoid` for the new NumPy version.
- Dependencies come from the unchanged upstream frozen lock: Brahe 1.1.4,
  NumPy 2.4.3 and SciPy 1.17.1 in this installation.

Our country constraints, supplied LEO/MEO/GEO/HEO two-body examples, scheduled
placement objective, and RF scenario model remain in `src/network_design`.
These are our extensions, not claims about the authors' paper implementation.

## Run from this directory

```sh
uv sync --frozen
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python local_tools/run_upstream.py
.venv/bin/python local_tools/check_design_upstream.py
MPLCONFIGDIR="$PWD/.cache/matplotlib" .venv/bin/python local_tools/run_design.py \
  config/design/meo_rf.json --output local_runs/adoption_oct2026/meo_rf
```

CBC must be installed. The wrapper adds `/opt/homebrew/bin` to PATH on macOS.
Current upstream output goes to `local_runs/upstream_oct2026`; extension migration
output goes to `local_runs/adoption_oct2026`. All runs use bundled snapshots.

## Scientific interpretation

The authors' placement objective and refinement acceptance use raw contact time;
contact exclusion is applied afterward. Our extension optimizes scheduled volume
and enforces country/spacing constraints. Their results are not interchangeable.
The upstream docstrings identify remaining initialization/tolerance/penalty issues;
adoption preserves those behaviors rather than silently changing the reference.
Our additional orbit and atmospheric models remain exploratory, as before.

Old and new Brahe versions need not produce identical contact boundaries. Validate
our adapter against the *current* upstream using identical satellites and windows.

## Additional upstream scheduling issue found during migration

Brahe 1.1.4 gives a newly constructed `PointLocation` no numeric ID by default.
Upstream's `contactExclusion` groups contacts by `location_id`, so several such
stations are treated as one resource (`None`). In the three-station/two-satellite
check, this reduces reported scheduled volume. Our evaluator already uses explicit
station indices. The cross-check now records both the unchanged upstream result
and the result with `.with_id(i)` on each station; only the latter is the correct
multi-station comparison. No upstream source was patched during adoption.

Before using upstream's multi-station reported throughput as a scientific benchmark,
apply and document this identity fix on a separate change, or use our identified
network evaluator. The one-station upstream smoke test is unaffected.

## Completed validation

- 14 unit/behavioral tests pass with the new lockfile, including the RF integral.
- Unmodified upstream SCORE completes selection and refinement: 351 evaluations,
  12 scheduled contacts, 5,936,816,162,109.375 bits (0.742102 TB).
- Our adapter exactly matches that single-station scheduled volume.
- Three-station evaluation with explicit identities: upstream CBC and our HiGHS
  both return 10,147,795,532,226.562 bits. The unlabelled upstream comparison
  returns 9,544,617,553,710.938 bits, confirming the identity issue above.
- Our country-constrained search completes using the current upstream propagator.
- MEO RF demo completes at 0.138393 TB, consistent with the prior demonstration.
- `git diff --exit-code` passes: tracked upstream files remain unchanged.

Evidence: `local_runs/adoption_oct2026/` and
`local_runs/upstream_oct2026/adapter_check.json`.
