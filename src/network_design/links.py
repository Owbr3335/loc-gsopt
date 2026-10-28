"""RF engineering scenario model; atmospheric inputs are prescribed, not forecasts."""
from dataclasses import dataclass
import math
import numpy as np

@dataclass(frozen=True)
class RFSettings:
    frequency_ghz: float = 8.2
    eirp_dbw: float = 20
    receive_gt_db_k: float = 20
    required_ebn0_db: float = 5
    implementation_margin_db: float = 3
    other_loss_db: float = 2
    zenith_atmospheric_loss_db: float = 0.2
    additional_weather_loss_db: float = 0
    availability: float = 1
    integration_step_s: float = 30

    def __post_init__(self):
        if not all(math.isfinite(v) for v in self.__dict__.values()):
            raise ValueError('RF inputs must be finite')
        if self.frequency_ghz<=0 or self.integration_step_s<=0 or not 0<=self.availability<=1:
            raise ValueError('Invalid RF frequency, time step or availability')
        if min(self.implementation_margin_db,self.other_loss_db,self.zenith_atmospheric_loss_db,self.additional_weather_loss_db)<0:
            raise ValueError('Losses and margin must be nonnegative')

class RFLink:
    def __init__(self, provider, settings=None):
        self.provider, self.settings = provider, settings or RFSettings()

    def rate(self, distance_m, elevation_deg, cap_bps):
        s = self.settings
        fspl = 20*np.log10(4*np.pi*np.asarray(distance_m)*s.frequency_ghz*1e9/299792458)
        atmosphere = s.zenith_atmospheric_loss_db/np.maximum(np.sin(np.deg2rad(elevation_deg)),0.01)
        cn0 = s.eirp_dbw+s.receive_gt_db_k-fspl-s.other_loss_db-atmosphere-s.additional_weather_loss_db+228.6
        rate = 10**(np.clip((cn0-s.required_ebn0_db-s.implementation_margin_db)/10,-30,30))
        return np.minimum(cap_bps,rate)*s.availability

    def data_bits(self, contact, site):
        t = np.linspace(contact.start_s,contact.end_s,max(2,int(np.ceil((contact.end_s-contact.start_s)/self.settings.integration_step_s))+1))
        distance,elevation = self.provider.geometry(site,contact.satellite,t)
        rates = self.rate(distance,elevation,min(contact.satellite_rate_bps,contact.station_rate_bps))
        return float(np.trapezoid(rates,t))
