# Current upstream baseline — adopted October 27, 2026

The active checkout now uses upstream commit
`2d1411ab9b479e6a7cc76597a390943d4e0c5956` (October 25, 2026), shared by
`gkim65/loc-gsopt` and `sisl/loc-gsopt`. The old sequential-only comparison below
is historical and does **not** describe the current upstream implementation.

The updated upstream includes the MIT license (copyright Grace Ra Kim), citation
metadata, SCORE cyclic refinement with Nelder–Mead/Powell, differential evolution,
a working fixed-site MILP entry point, paper result data and figure scripts.
See `ADOPTION.md` for current commands, compatibility changes and validation.

---

# Stanford repository and our prototype

Inspected 2026-10-13. Upstream: https://github.com/sisl/loc-gsopt
Commit: `249f5315ae056653ef3e981cee6f2d60816e96ce` (2025-04-27).
Paper: https://arxiv.org/html/2606.12667v1 (2026).

## What was corrected

We originally cloned `ground-station-optimizer`, supporting the older fixed-site
selection paper, then wrote an independent SCORE adaptation from the newer paper.
The newer paper does link to this separate `loc-gsopt` repository. We should have
inspected it before reimplementing SCORE. Both projects are retained side by side.

## What the public checkout actually implements

| Aspect | Stanford checkout | Our `ground-station-optimizer` extension |
|---|---|---|
| Sequential placement | Yes: `src/methods/free_select/nelder_mead_scipy.py` | Yes: `gsopt/score.py` |
| Cyclic refinement | Explicit TODO before `nelder_mead_scipy`; the function returns after adding stations | Implemented, revisiting one station at a time |
| Local search | SciPy Nelder-Mead on unit-sphere coordinates | SciPy Nelder-Mead on unit-sphere coordinates |
| Starting points | Broad initial simplex selected from 40 sampled points | Multiple feasible starts and smaller local simplexes |
| Placement objective | Sum of raw contact seconds plus geographic penalties | Conflict-free scheduled data volume for every trial network |
| Contact scheduling | Separate CBC `contactExclusion` routine; called for reporting in the W&B-enabled main path, not inside the data placement objective | SciPy/HiGHS scheduling inside the placement objective |
| Land and spacing | Soft penalties | Hard rejection and final validation |
| Country minimums/maximums | Not found in inspected placement code | Implemented |
| Link model | Uniform configured rate; placement ranks raw duration | Fixed-rate interface for future link models |
| Configuration | Hydra YAML | JSON and typed search settings |
| Country polygons | Bundled 1:10m geometry; country attributes are absent from the checkout | Natural Earth 1:110m geometry with country codes |

This is a comparison of the downloaded code, not a claim that the paper's
experiments used exactly this checkout. The public commit predates the paper;
we have not verified whether a later research implementation exists elsewhere.
The paper describes cyclic refinement, whereas this checkout does not implement it.

Further issues to audit before building on the source:

- The local search passes `xtol`/`ftol`; modern SciPy Nelder-Mead uses
  `xatol`/`fatol`. Do not assume the intended tolerances are applied.
- `simplex_select` constructs latitude/longitude pairs, but conversion at
  `nelder_mead_scipy.py:123` passes them in reversed order to `latlon_to_xyz`.
  This affects initialization, not the final conversion back to station coordinates.
- The raw-duration objective can reward overlapping access opportunities. Reported
  throughput must be calculated separately with scheduling exclusions.
- The objective uses squared kilometers for the water penalty and squared meters
  for station separation. Their relative weighting deserves explicit review.

## Running the original code

Dependencies are isolated in `.venv`, installed from the unchanged `uv.lock`.
Brahe is pinned by that lock to `98b732fa196c71f9300eb04f77d8d70046a63e29`.
The original source, config, and dependency lock have not been edited.

From this directory:

```sh
MPLCONFIGDIR="$PWD/.cache/matplotlib" WANDB_MODE=disabled \
  .venv/bin/python src/main.py debug.wandb=false debug.plot=false \
  debug.verbose=false problem.gs_num=1
```

This runs the bundled one-satellite UMBRA scenario for April 1–2, 2025, selecting
one station. Online logging and data refresh are disabled. The original default
config enables W&B and names the authors' account; use the overrides above.
The one-station original-entry-point smoke test completed successfully, reporting
87 iterations, 191 evaluations and objective -1221.190796. That objective is in
raw contact seconds plus penalties, not TB.

To save inspectable artifacts, use our separate wrapper:

```sh
MPLCONFIGDIR="$PWD/.cache/matplotlib" WANDB_MODE=disabled \
  .venv/bin/python -u local_tools/run_upstream.py --sites 2
```

The wrapper directly calls the original placement function and saves the resolved
configuration, satellite inputs, coordinates, raw access totals, GeoJSON and map
under `local_runs/upstream_example/`. It does not implement or inject refinement,
country constraints, solver fixes, or any substitute objective.

## Integration decision

Use this checkout as the upstream reference and baseline, not as evidence that
we have reproduced the full paper. Before merging extensions:

1. Verify whether the authors have a newer implementation with cyclic refinement.
2. Add regression tests for the upstream coordinate and objective behavior, then
   make compatibility/bug fixes explicitly rather than silently changing a baseline.
3. Bring over country constraints and scheduling evaluation as separate, tested
   modules; decide explicitly whether to retain penalties for other site restrictions.
4. Add the paper's cyclic stage if no newer source is available.
5. Validate supplied MEO/GEO/HEO orbits and add link-budget models afterward.

Our existing country requirements, evaluator tests and configuration design remain
useful. Neither codebase currently establishes validated MEO/GEO/HEO or detailed
atmospheric-link capability. No throughput advantage between the implementations
has been established: their existing demos differ in satellites, dates, number of
stations, constraints and objective calculations.

## Saved two-station result

The unmodified placement function completed in about 76 seconds for two stations,
using 191 and 151 function evaluations respectively. Saved coordinates:
(116.4780374 E, -35.0082472 latitude) and (149.4766776 E, 75.2554581 latitude).
The run yielded 14 contacts and 0.73649432385 TB of raw access volume.

`local_tools/check_schedule.py` independently applies Stanford's CBC scheduler
and our HiGHS scheduler to these same contacts. Both selected all 14 and returned
exactly 5,891,954,590,800 bits. This particular example had no scheduling reduction;
it does not prove raw access objectives are safe for other networks. The check
uses the upstream strict >180-second rule; our original demo uses >=180 seconds.

```sh
PATH="/opt/homebrew/bin:$PATH" MPLCONFIGDIR="$PWD/.cache/matplotlib" \
  .venv/bin/python local_tools/check_schedule.py
```

Artifacts: `local_runs/upstream_example/result.json`, `config.yaml`,
`stations.geojson`, `network.png`, and `schedule_check.json`.
The original entry-point and wrapper logs are retained in `local_runs/`.
`git diff --exit-code` confirms all tracked upstream files remain unchanged.
