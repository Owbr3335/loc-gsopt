"""Supplied elliptic two-body orbits. SI units; epoch-relative ECI and rotating Earth.

Exploratory model: no perturbations, terrain, refraction or precision EOP. Rotation
angle at epoch is an explicit input. TLE mean elements must not be used here.
"""
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np
from scipy.optimize import brentq
from .evaluation import Pass

MU = 3.986004418e14
EARTH_A = 6378137.0
EARTH_E2 = 6.69437999014e-3
OMEGA = 7.2921150e-5

@dataclass(frozen=True)
class Orbit:
    name: str
    semi_major_axis_km: float
    eccentricity: float = 0
    inclination_deg: float = 0
    raan_deg: float = 0
    argument_perigee_deg: float = 0
    mean_anomaly_deg: float = 0
    rate_bps: float = 1.2e9

    def __post_init__(self):
        values = list(self.__dict__.values())[1:]
        if not self.name or not all(math.isfinite(v) for v in values):
            raise ValueError('Orbit requires a name and finite elements')
        if not 0 <= self.eccentricity < 1 or not 0 <= self.inclination_deg <= 180:
            raise ValueError('Expected elliptic orbit and inclination in [0,180]')
        if self.semi_major_axis_km*1000*(1-self.eccentricity) <= EARTH_A or self.rate_bps <= 0:
            raise ValueError('Perigee must be above Earth and rate positive')

    @property
    def period_s(self):
        return 2*np.pi*np.sqrt((self.semi_major_axis_km*1000)**3/MU)

    def position(self, seconds):
        t = np.asarray(seconds)
        m = np.remainder(np.deg2rad(self.mean_anomaly_deg)+2*np.pi*t/self.period_s, 2*np.pi)
        # Bracketed vector bisection remains stable for highly eccentric orbits.
        lo, hi = np.zeros_like(m), np.full_like(m, 2*np.pi)
        for _ in range(48):
            mid = (lo+hi)/2
            left = mid-self.eccentricity*np.sin(mid) < m
            lo, hi = np.where(left, mid, lo), np.where(left, hi, mid)
        e = (lo+hi)/2
        a = self.semi_major_axis_km*1000
        xy = np.stack([a*(np.cos(e)-self.eccentricity), a*np.sqrt(1-self.eccentricity**2)*np.sin(e), np.zeros_like(e)], axis=-1)
        r, i, w = np.deg2rad([self.raan_deg,self.inclination_deg,self.argument_perigee_deg])
        def rz(x):
            return np.array([[np.cos(x),-np.sin(x),0],[np.sin(x),np.cos(x),0],[0,0,1]])
        rx = np.array([[1,0,0],[0,np.cos(i),-np.sin(i)],[0,np.sin(i),np.cos(i)]])
        return xy @ (rz(r) @ rx @ rz(w)).T

class OrbitContacts:
    def __init__(self, orbits, duration_s=86400, step_s=60, elevation_min_deg=10,
                 earth_angle_deg=0, station_rate_bps=1.2e9):
        if not orbits or len({o.name for o in orbits}) != len(orbits):
            raise ValueError('Supply uniquely named orbits')
        if not all(math.isfinite(v) for v in [duration_s,step_s,elevation_min_deg,earth_angle_deg,station_rate_bps]):
            raise ValueError('Nonfinite propagation settings')
        if duration_s <= 0 or step_s <= 0 or station_rate_bps <= 0 or not 0 <= elevation_min_deg < 90:
            raise ValueError('Invalid propagation settings')
        self.orbits = {o.name:o for o in orbits}
        self.duration_s, self.step_s = duration_s, step_s
        self.elevation_min_deg, self.earth_angle_deg = elevation_min_deg, earth_angle_deg
        self.station_rate_bps = station_rate_bps
        self.times = np.linspace(0,duration_s,int(np.ceil(duration_s/step_s))+1)
        self.positions = {o.name:o.position(self.times) for o in orbits}

    def geometry(self, site, satellite, seconds, position=None):
        t = np.asarray(seconds)
        lon, lat = np.deg2rad([site.longitude,site.latitude])
        angle = lon+np.deg2rad(self.earth_angle_deg)+OMEGA*t
        n = EARTH_A/np.sqrt(1-EARTH_E2*np.sin(lat)**2)
        ground = np.stack([n*np.cos(lat)*np.cos(angle),n*np.cos(lat)*np.sin(angle),np.full_like(angle,n*(1-EARTH_E2)*np.sin(lat))],axis=-1)
        up = np.stack([np.cos(lat)*np.cos(angle),np.cos(lat)*np.sin(angle),np.full_like(angle,np.sin(lat))],axis=-1)
        delta = (self.orbits[satellite].position(t) if position is None else position)-ground
        distance = np.linalg.norm(delta,axis=-1)
        elevation = np.rad2deg(np.arcsin(np.clip(np.sum(delta*up,axis=-1)/distance,-1,1)))
        return distance, elevation

    @lru_cache(maxsize=4096)
    def contacts(self, site):
        contacts = []
        for name, orbit in self.orbits.items():
            _, el = self.geometry(site,name,self.times,self.positions[name])
            above = el >= self.elevation_min_deg
            roots = []
            for j in np.flatnonzero(above[1:] != above[:-1]):
                roots.append(brentq(lambda t: float(self.geometry(site,name,t)[1])-self.elevation_min_deg,self.times[j],self.times[j+1],xtol=1e-5))
            boundaries = [0,*roots,self.duration_s]
            for a,b in zip(boundaries,boundaries[1:]):
                if b>a and self.geometry(site,name,(a+b)/2)[1]>=self.elevation_min_deg:
                    contacts.append(Pass(name,a,b,orbit.rate_bps,self.station_rate_bps))
        return tuple(contacts)
