"""Friendly expansion inputs normalized into the existing design configuration."""
from copy import deepcopy
from .geography import Site
from .orbits import EARTH_A, Orbit

PRESETS = {'LEO': {'altitude_km':550,'inclination_deg':53},
           'MEO': {'altitude_km':20200,'inclination_deg':55}}

def normalize(config):
    """Return resolved config and named fixed stations. Country rules cover all sites."""
    c=deepcopy(config)
    existing=c.get('existing_sites',[])
    names=[]
    for row in existing:
        if set(row)-{'name','longitude','latitude'}:
            raise ValueError('Existing sites accept name, longitude and latitude only')
        if not isinstance(row.get('name'),str) or not row['name'].strip():
            raise ValueError('Every existing site needs a name')
        Site(row['longitude'],row['latitude'])
        names.append(row['name'])
    if len(set(names))!=len(names):
        raise ValueError('Existing site names must be unique')
    geography=c.setdefault('geography',{})
    if 'new_sites' in c:
        n=c['new_sites']
        if type(n) is not int or n<0:raise ValueError('new_sites must be a nonnegative integer')
        total=len(existing)+n
        if 'station_count' in geography and geography['station_count']!=total:
            raise ValueError('station_count must equal existing sites plus new_sites')
        geography['station_count']=total
    elif existing:
        raise ValueError('Specify new_sites when supplying existing_sites (0 evaluates the existing network)')
    if 'satellites' in c and 'orbits' in c:
        raise ValueError('Supply satellites or orbits, not both')
    if 'satellites' in c:
        orbits=[]
        for row in c.pop('satellites'):
            row=dict(row)
            preset=row.pop('preset',None)
            if preset is not None and preset not in PRESETS:
                raise ValueError('Satellite preset must be LEO or MEO')
            defaults=dict(PRESETS.get(preset,{}))
            if 'semi_major_axis_km' in row:defaults.pop('altitude_km',None)
            defaults.update(row)
            if 'altitude_km' in defaults:
                if 'semi_major_axis_km' in defaults:
                    raise ValueError('Supply altitude_km or semi_major_axis_km, not both')
                if defaults.get('eccentricity',0)!=0:
                    raise ValueError('For eccentric orbits specify semi_major_axis_km explicitly')
                defaults['semi_major_axis_km']=EARTH_A/1000+defaults.pop('altitude_km')
            Orbit(**defaults)
            orbits.append(defaults)
        c['orbits']=orbits
    return c,existing
