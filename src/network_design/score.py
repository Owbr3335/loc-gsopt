"""SCORE sequential placement and cyclic refinement, adapted from arXiv:2606.12667.

Hard geographic rejection replaces the paper's geographic penalties. Search is
heuristic: termination does not certify a global or local optimum.
"""
from dataclasses import dataclass, asdict
import math
import numpy as np
from scipy.optimize import minimize
from .geography import Site


@dataclass
class SearchSettings:
    seed: int = 42
    starts_per_move: int = 3
    evaluations_per_start: int = 40
    max_cycles: int = 2
    improvement_tolerance: float = 1e-8

    def __post_init__(self):
        for name in ('starts_per_move', 'evaluations_per_start', 'max_cycles'):
            value = getattr(self, name)
            if type(value) is not int or value < (0 if name == 'max_cycles' else 1):
                raise ValueError(f"Invalid {name}")
        if not math.isfinite(self.improvement_tolerance) or self.improvement_tolerance < 0:
            raise ValueError("Invalid improvement_tolerance")


def vector(site):
    lon, lat = np.radians([site.longitude, site.latitude])
    return np.array([np.cos(lat)*np.cos(lon), np.cos(lat)*np.sin(lon), np.sin(lat)])


def coordinates(v):
    norm = np.linalg.norm(v)
    if not np.isfinite(norm) or norm < 1e-12:
        return None
    x, y, z = v/norm
    return Site(float(np.degrees(np.arctan2(y, x))), float(np.degrees(np.arcsin(np.clip(z, -1, 1)))))


class ScoreOptimizer:
    def __init__(self, objective, geography, settings=None, progress=None):
        self.objective = objective  # callable(network) -> finite scalar, higher is better
        self.geography = geography
        self.settings = settings or SearchSettings()
        self.progress = progress or (lambda event: None)

    def solve(self, existing_sites=()):
        rng = np.random.default_rng(self.settings.seed)
        sites = list(existing_sites)
        existing_count = len(sites)
        violations = self.geography.violations(sites, complete=False)
        if violations:
            raise ValueError(f"Existing sites conflict with final-network requirements: {violations}")
        history = []
        evaluations = 0

        def evaluate(network):
            nonlocal evaluations
            value = float(self.objective(network))
            evaluations += 1
            if not math.isfinite(value):
                raise ValueError("Objective returned a non-finite value")
            return value

        def move(fixed, incumbent=None):
            best_site = incumbent
            best_value = evaluate([*fixed, incumbent]) if incumbent is not None else -math.inf

            def loss(v):
                nonlocal best_site, best_value
                candidate = coordinates(v)
                if candidate is None or self.geography.violations([*fixed, candidate], complete=False):
                    return 1e100
                value = evaluate([*fixed, candidate])
                if value > best_value:
                    best_site, best_value = candidate, value
                return -value

            starts = ([incumbent] if incumbent is not None else [])
            starts += [self.geography.sample_candidate(rng, fixed) for _ in range(self.settings.starts_per_move)]
            for start in starts:
                x = vector(start)
                loss(x)  # always retain a feasible seed even with a tiny search budget
                simplex = np.vstack([x, x + np.eye(3)*0.15])
                minimize(loss, x, method='Nelder-Mead', options={
                    'maxfev': self.settings.evaluations_per_start,
                    'initial_simplex': simplex, 'xatol': 1e-5, 'fatol': self.settings.improvement_tolerance,
                })
            return best_site, best_value

        def record(phase, cycle, value):
            event = {'phase': phase, 'cycle': cycle, 'objective': value,
                     'evaluations': evaluations, 'sites': [asdict(s) for s in sites]}
            history.append(event)
            self.progress(event)

        value = evaluate(sites)
        baseline_value = value
        record('existing', 0, value)
        for _ in range(self.geography.station_count-existing_count):
            site, value = move(sites)
            sites.append(site)
            record('selection', 0, value)

        stop_reason = 'cycle_budget'
        for cycle in range(1, self.settings.max_cycles+1):
            changed = False
            for i in rng.permutation(np.arange(existing_count, len(sites))):
                fixed = sites[:i] + sites[i+1:]
                candidate, candidate_value = move(fixed, sites[i])
                if candidate_value > value + self.settings.improvement_tolerance:
                    sites[i], value = candidate, candidate_value
                    changed = True
                record('refinement', cycle, value)
            if not changed:
                stop_reason = 'no_improvement_found'
                break

        violations = self.geography.violations(sites)
        if violations:
            raise RuntimeError(f"Final constraint validation failed: {violations}")
        return {'status': 'best_found', 'stop_reason': stop_reason, 'objective': value,
                'existing_count': existing_count, 'existing_objective': baseline_value,
                'sites': [asdict(s) for s in sites], 'country_counts': dict(self.geography.counts(sites)),
                'constraint_violations': violations, 'evaluations': evaluations, 'history': history,
                'search_settings': asdict(self.settings)}
