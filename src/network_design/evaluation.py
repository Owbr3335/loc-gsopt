"""Contact/link interfaces and exact whole-contact scheduling for SCORE.

Only the contact provider knows about orbits. SCORE never changes an orbit.
"""
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol
import math
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix


@dataclass(frozen=True)
class Pass:
    satellite: str
    start_s: float
    end_s: float
    satellite_rate_bps: float
    station_rate_bps: float


class ContactProvider(Protocol):
    def contacts(self, site) -> tuple[Pass, ...]: ...


class LinkModel(Protocol):
    def data_bits(self, contact: Pass, site) -> float: ...


class FixedRateLink:
    def data_bits(self, contact, site):
        return (contact.end_s-contact.start_s)*min(contact.satellite_rate_bps, contact.station_rate_bps)


def schedule(contacts, volumes):
    """Maximize bits subject to one satellite/station contact at a time.

contacts are (station_index, Pass). Half-open intervals allow back-to-back passes.
An optimality certificate applies only to this fixed-network scheduling problem.
"""
    n = len(contacts)
    if not n:
        return 0.0, []
    volumes = np.asarray(volumes, dtype=float)
    if len(volumes) != n or np.any(~np.isfinite(volumes)) or np.any(volumes < 0):
        raise ValueError("Link volumes must be finite and nonnegative")
    if any(not math.isfinite(c.start_s) or not math.isfinite(c.end_s) or c.end_s <= c.start_s for _, c in contacts):
        raise ValueError("Contact intervals must be finite and positive")
    rows, columns, row = [], [], 0
    for i, (station_i, a) in enumerate(contacts):
        for j in range(i+1, n):
            station_j, b = contacts[j]
            if (station_i == station_j or a.satellite == b.satellite) and max(a.start_s, b.start_s) < min(a.end_s, b.end_s):
                rows.extend([row, row]); columns.extend([i, j]); row += 1
    matrix = coo_matrix((np.ones(len(rows)), (rows, columns)), shape=(row, n)).tocsc()
    constraints = LinearConstraint(matrix, -np.inf, 1) if row else None
    # Normalize only for numeric conditioning, not to alter the objective.
    scale = max(float(volumes.max()), 1.0)
    result = milp(-volumes/scale, integrality=np.ones(n), bounds=Bounds(0, 1),
                  constraints=constraints, options={'mip_rel_gap': 0.0})
    if not result.success:
        raise RuntimeError(f"Contact scheduling did not solve optimally: {result.message}")
    selected = np.flatnonzero(result.x > 0.5).tolist()
    return float(volumes[selected].sum()), selected


class NetworkEvaluator:
    def __init__(self, provider: ContactProvider, link: LinkModel, minimum_contact_s=180):
        self.provider, self.link = provider, link
        if not math.isfinite(minimum_contact_s) or minimum_contact_s < 0:
            raise ValueError("minimum_contact_s must be finite and nonnegative")
        self.minimum_contact_s = minimum_contact_s

    def details(self, sites):
        contacts, volumes = [], []
        for i, site in enumerate(sites):
            for c in self.provider.contacts(site):
                if c.end_s-c.start_s >= self.minimum_contact_s:
                    contacts.append((i, c))
                    volumes.append(self.link.data_bits(c, site))
        bits, selected = schedule(contacts, volumes)
        return {'data_bits': bits, 'data_TB': bits/8e12, 'eligible_contacts': len(contacts),
                'selected_contacts': [dict(station_index=contacts[i][0], satellite=contacts[i][1].satellite,
                                           start_s=contacts[i][1].start_s, end_s=contacts[i][1].end_s,
                                           data_bits=volumes[i]) for i in selected]}

    def __call__(self, sites):
        return self.details(sites)['data_TB']
