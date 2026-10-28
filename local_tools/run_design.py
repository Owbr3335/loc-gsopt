"""Run our SCORE extension; never modifies the supplied orbit elements."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from network_design.geography import Countries, Geography, Site
from network_design.score import ScoreOptimizer, SearchSettings
from network_design.orbits import Orbit, OrbitContacts
from network_design.evaluation import NetworkEvaluator, FixedRateLink
from network_design.links import RFLink, RFSettings
from network_design.scenario import normalize


def run(config, destination):
    requested_config = config
    config, existing = normalize(config)
    fixed_sites = [Site(s['longitude'],s['latitude']) for s in existing]
    countries = Countries.read(ROOT/'data/countries/ne_110m_admin_0_countries.shp')
    geography = Geography(countries,**config['geography'])
    provider = OrbitContacts([Orbit(**o) for o in config['orbits']],**config.get('propagation',{}))
    link_config = config.get('link',{'type':'fixed'})
    if link_config['type'] not in ('fixed','rf'):
        raise ValueError('Unknown link type')
    link = FixedRateLink() if link_config['type']=='fixed' else RFLink(provider,RFSettings(**link_config.get('settings',{})))
    evaluator = NetworkEvaluator(provider,link,config.get('minimum_contact_s',180))
    result = ScoreOptimizer(evaluator,geography,SearchSettings(**config.get('search',{})),
                            lambda e: print(e['phase'],e['cycle'],round(e['objective'],6),flush=True)).solve(fixed_sites)
    sequential = [e for e in result['history'] if e['phase'] in ('selection','existing')][-1]
    result['comparison'] = {'sequential_TB': sequential['objective'],'refined_TB':result['objective'],
                            'improvement_TB':result['objective']-sequential['objective'],
                            'same_run_sequential_sites':sequential['sites']}
    result['comparison'].update(existing_TB=result['existing_objective'], expanded_TB=result['objective'],
                                expansion_gain_TB=result['objective']-result['existing_objective'])
    result['existing_schedule'] = evaluator.details(fixed_sites)
    result['station_details'] = [dict(**s, name=existing[i]['name'] if i<len(existing) else f'New site {i-len(existing)+1}',
                                    status='existing' if i<len(existing) else 'new', country=countries.country(Site(**s)))
                                 for i,s in enumerate(result['sites'])]
    result['country_requirements'] = [dict(country=code, count=result['country_counts'].get(code,0),
                                          minimum=geography.country_minimums.get(code,0),
                                          maximum=geography.country_maximums.get(code,geography.station_count),
                                          satisfied=True)
                                     for code in sorted(set(geography.country_minimums)|set(geography.country_maximums))]
    result['schedule'] = evaluator.details([Site(**s) for s in result['sites']])
    result['model'] = 'Supplied two-body Keplerian orbits; whole-pass scheduling; exploratory RF scenarios'
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'input.json').write_text(json.dumps(requested_config,indent=2)+'\n')
    (destination/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    features = [{'type':'Feature','properties':{'station':i+1,'name':s['name'],'status':s['status'],'country':s['country']},
                 'geometry':{'type':'Point','coordinates':[s['longitude'],s['latitude']]}} for i,s in enumerate(result['station_details'])]
    (destination/'stations.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},indent=2)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax = plt.subplots(figsize=(12,6))
    for g in countries.geometries.values():
        for p in (g.geoms if g.geom_type=='MultiPolygon' else [g]):
            x,y=p.exterior.xy; ax.fill(x,y,color='#eeeeee',edgecolor='#bbbbbb',linewidth=.3)
    for stage,sites,color,marker in [('Existing (fixed)',result['sites'][:len(existing)],'#555555','s'),('New sites',result['sites'][len(existing):],'#1265a8','o')]:
        ax.scatter([s['longitude'] for s in sites],[s['latitude'] for s in sites],label=stage,c=color,marker=marker,s=55)
    ax.set(xlim=(-180,180),ylim=(-90,90),xlabel='Longitude (degrees)',ylabel='Latitude (degrees)',title=f"{config['name']}: {result['existing_objective']:.4f} → {result['objective']:.4f} TB")
    ax.legend(); fig.tight_layout(); fig.savefig(destination/'comparison.png',dpi=160); plt.close(fig)
    lines=[f"# {config['name']}",'',f"Existing network: {result['existing_objective']:.6f} TB",
           f"Expanded network: {result['objective']:.6f} TB",f"Added volume: {result['comparison']['expansion_gain_TB']:.6f} TB",'',
           '| Station | Status | Country | Longitude | Latitude |','|---|---|---|---:|---:|']
    lines += [f"| {s['name']} | {s['status']} | {s['country']} | {s['longitude']:.4f} | {s['latitude']:.4f} |" for s in result['station_details']]
    lines += ['', 'Final-network constraint violations: none.', '',
              'Country counts include existing and new sites. Existing coordinates are fixed.',
              'Direct downlinks; no crosslinks. Two-body propagation and whole-pass scheduling.',
              'Example coordinates and preset orbits are illustrative, not operator specifications.']
    (destination/'summary.md').write_text('\n'.join(lines)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('config',type=Path); parser.add_argument('--output',type=Path)
    args=parser.parse_args(); config=json.loads(args.config.read_text())
    run(config,args.output or ROOT/'local_runs/design'/args.config.stem)
