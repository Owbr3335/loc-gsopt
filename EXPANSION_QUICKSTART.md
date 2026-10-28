# Expand an existing LEO/MEO ground network

Start with `config/design/expand_five_sites.json`. It contains five **illustrative**
existing sites, one LEO satellite, one MEO satellite and two new stations to place.
Replace the example names and coordinates with your own sites.

From this repository:

```sh
MPLCONFIGDIR="$PWD/.cache/matplotlib" .venv/bin/python local_tools/run_design.py \
  config/design/expand_five_sites.json --output local_runs/expansion/five_sites
```

Open `local_runs/expansion/five_sites/summary.md` for the before/after comparison,
`comparison.png` for the map and `stations.geojson` for GIS import. `result.json`
contains selected contacts, country counts, requirements and search history.
`input.json` saves your input; `config.json` records resolved orbit elements.
Results use decimal TB (8 trillion bits), over the configured simulation window.

## The four things to edit

1. **existing_sites:** name, longitude and latitude in decimal degrees (west/south
   negative). These stations are used in the baseline and never moved or removed.
2. **new_sites:** the number of stations to add, not the final total. Set to zero
   to evaluate the existing network; all final-network country rules must then
   already be satisfied.
3. **satellites:** add a named entry with `"preset": "MEO"` or `"preset": "LEO"`.
   Both kinds can appear in the same list. Names must be unique.
4. **geography:** `country_minimums`, `country_maximums`, `excluded_countries`,
   and `min_separation_km`. Country codes come from the supplied Natural Earth
   ADM0_A3 data; examples are USA, AUS, ESP, ZAF and JPN.

```json
"satellites": [
  {"name": "LEO-1", "preset": "LEO"},
  {"name": "MEO-1", "preset": "MEO", "altitude_km": 20200,
   "inclination_deg": 55, "raan_deg": 90, "mean_anomaly_deg": 180}
]
```

The example LEO preset is circular at 550 km, inclination 53 degrees. MEO is
circular at 20,200 km, inclination 55 degrees. Both default to RAAN, argument of
perigee and mean anomaly zero, and 1.2 Gbps. These are editable demonstration
orbits, not imported operational constellations. For an eccentric orbit supply
`semi_major_axis_km` and `eccentricity` instead of `altitude_km`. Existing `orbits`
configs still work; do not supply both `orbits` and `satellites`.

## How country requirements work

Country minimums and maximums count **existing plus new** stations. In the example,
there are already two USA sites, so minimum USA=1 is satisfied and maximum USA=2
prevents any additional USA placement. Minimum AUS=1 requires an Australian site.
The optimizer is free to choose the other addition within the remaining rules.

Exclusions, land eligibility and minimum separation also apply to the entire
network. Existing violations fail clearly rather than being silently exempted.
Co-located antennas should not be entered as separate sites in this single-antenna
model. Boundaries are coarse demonstration polygons; near-coast and disputed-border
sites may need better boundary data. Search exhaustion is not proof of infeasibility.

## Current model

Only direct satellite-to-ground links are evaluated. Orbits are supplied inputs,
not optimization decisions. Every station and satellite supports one scheduled
contact at a time. Scheduling selects whole passes and cannot split long MEO
passes for handovers; this can underestimate achievable performance. The first
version uses a common fixed data rate, two-body orbits and a defined Earth rotation
angle at time zero (default zero), with no crosslinks or weather prediction.
Country feasibility does not imply that a station provides a minimum service level.

Separate orbit, contact, link and scheduling modules remain available for future
crosslink/routing work. Crosslinks are not activated by these inputs.
