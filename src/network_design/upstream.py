"""Brahe 1.x adapter using upstream access calculations and supplied propagators.

Initialize Earth orientation data before constructing this adapter. No TLE or EOP
files are downloaded. Satellites are propagated through the supplied window.
"""
from functools import lru_cache
import math
from .evaluation import Pass

class UpstreamContacts:
    def __init__(self, satellites, start, end, rate_bps=1.2e9, elevation_min_deg=10):
        import brahe as bh
        if not satellites or end-start<=0 or not math.isfinite(rate_bps) or rate_bps<=0 or not 0<=elevation_min_deg<90:
            raise ValueError('Invalid upstream contact inputs')
        self.satellites,self.start,self.end=satellites,start,end
        self.rate_bps,self.elevation_min_deg=rate_bps,elevation_min_deg
        bh.par_propagate_to(satellites,end)

    @lru_cache(maxsize=4096)
    def contacts(self,site):
        import brahe as bh
        from common.utils import compute_contact_times
        station=bh.PointLocation(site.longitude,site.latitude)
        result=[]
        # Assign stable per-provider identities even when propagators lack IDs.
        for index,satellite in enumerate(self.satellites):
            windows,_=compute_contact_times([satellite],[station],self.start,self.end,self.elevation_min_deg)
            for c in windows:
                a=max(0,float(c.t_start-self.start))
                b=min(float(self.end-self.start),float(c.t_end-self.start))
                if b>a:
                    result.append(Pass(str(index),a,b,self.rate_bps,self.rate_bps))
        return tuple(result)
