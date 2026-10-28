"""Hard country-count and separation constraints for continuous placement.

Boundaries are a modeling input, not a statement about disputed sovereignty.
Natural Earth 1:110m is suitable for demonstrations, not parcel selection.
"""
from collections import Counter
from dataclasses import dataclass, field
import math
from pathlib import Path

import numpy as np
from shapely.geometry import Point, shape
from shapely.ops import unary_union


@dataclass(frozen=True)
class Site:
    longitude: float
    latitude: float

    def __post_init__(self):
        if not (-180 <= self.longitude <= 180 and -90 <= self.latitude <= 90):
            raise ValueError("Site coordinates must be finite longitude/latitude degrees")


def distance_km(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, (a.longitude, a.latitude, b.longitude, b.latitude))
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


class Countries:
    def __init__(self, geometries, names=None):
        self.geometries = geometries
        self.names = names or {k: k for k in geometries}
        if not geometries or any(g.is_empty or not g.is_valid for g in geometries.values()):
            raise ValueError("Country polygons must be nonempty and valid")

    @classmethod
    def read(cls, path):
        """Read GeoJSON (country property) or Natural Earth shapefile (ADM0_A3)."""
        import json
        grouped = {}
        if Path(path).suffix.lower() == '.json' or Path(path).suffix.lower() == '.geojson':
            features = json.loads(Path(path).read_text())['features']
            records = [(f['properties']['country'], shape(f['geometry']), f['properties'].get('name', f['properties']['country'])) for f in features]
        else:
            from cartopy.io.shapereader import Reader
            records = [(r.attributes['ADM0_A3'], r.geometry, r.attributes['NAME_LONG']) for r in Reader(path).records()]
        names = {}
        for country, geometry, name in records:
            grouped.setdefault(country, []).append(geometry)
            names[country] = name
        return cls({k: unary_union(v) for k, v in grouped.items()}, names)

    def country(self, site):
        point = Point(site.longitude, site.latitude)
        matches = [k for k, g in self.geometries.items() if g.covers(point)]
        # Do not assign ambiguous shared borders to either country.
        return matches[0] if len(matches) == 1 else None

    def sample(self, rng, country=None):
        if country is None:
            # Uniform on the sphere, rejecting water in the caller.
            return Site(float(rng.uniform(-180, 180)), float(np.degrees(np.arcsin(rng.uniform(-1, 1)))))
        geometry = self.geometries[country]
        parts = list(geometry.geoms) if geometry.geom_type == 'MultiPolygon' else [geometry]
        weights = np.array([g.area for g in parts]); weights /= weights.sum()
        for _ in range(10000):
            g = parts[rng.choice(len(parts), p=weights)]
            x0, y0, x1, y1 = g.bounds
            s = Site(float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)))
            if self.country(s) == country:
                return s
        raise RuntimeError(f"Unable to sample interior of {country}; check boundary geometry")


@dataclass
class Geography:
    countries: Countries
    station_count: int
    country_minimums: dict = field(default_factory=dict)
    country_maximums: dict = field(default_factory=dict)
    excluded_countries: tuple = ()
    min_separation_km: float = 100.0

    def __post_init__(self):
        if type(self.station_count) is not int or self.station_count < 1:
            raise ValueError("station_count must be a positive integer")
        if not math.isfinite(self.min_separation_km) or self.min_separation_km < 0:
            raise ValueError("min_separation_km must be finite and nonnegative")
        for code in set(self.country_minimums) | set(self.country_maximums) | set(self.excluded_countries):
            if code not in self.countries.geometries:
                raise ValueError(f"Unknown country code: {code}")
        for counts in (self.country_minimums, self.country_maximums):
            if any(type(v) is not int or v < 0 for v in counts.values()):
                raise ValueError("Country counts must be nonnegative integers")
        if sum(self.country_minimums.values()) > self.station_count:
            raise ValueError("Country minimums exceed total station count")
        for k, v in self.country_minimums.items():
            if v > self.country_maximums.get(k, self.station_count) or (v and k in self.excluded_countries):
                raise ValueError(f"Contradictory country requirements for {k}")
        capacity = sum(self.country_maximums.get(k, self.station_count)
                       for k in self.countries.geometries if k not in self.excluded_countries)
        if capacity < self.station_count:
            raise ValueError("Allowed country capacity is below station count")

    def counts(self, sites):
        return Counter(self.countries.country(s) for s in sites)

    def violations(self, sites, complete=True):
        errors = []
        counts = self.counts(sites)
        if len(sites) > self.station_count or (complete and len(sites) != self.station_count):
            errors.append("station count")
        if None in counts:
            errors.append("outside unambiguous country land polygons")
        if any(counts[k] for k in self.excluded_countries):
            errors.append("excluded country")
        if any(counts[k] > v for k, v in self.country_maximums.items()):
            errors.append("country maximum")
        deficit = sum(max(0, v-counts[k]) for k, v in self.country_minimums.items())
        if deficit > (0 if complete else self.station_count-len(sites)):
            errors.append("country minimum")
        if any(distance_km(a, b) < max(1e-6, self.min_separation_km)
               for i, a in enumerate(sites) for b in sites[i+1:]):
            errors.append("station separation")
        return errors

    def sample_candidate(self, rng, fixed):
        counts = self.counts(fixed)
        deficits = [k for k, v in self.country_minimums.items() if counts[k] < v]
        required = deficits[0] if deficits else None
        for _ in range(10000):
            candidate = self.countries.sample(rng, required)
            if not self.violations([*fixed, candidate], complete=False):
                return candidate
        raise RuntimeError("No feasible candidate found within sampling budget; constraints may be too restrictive. This is not a proof of infeasibility.")
