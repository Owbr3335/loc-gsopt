"""Compare our Brahe 1.x adapter with upstream contacts and CBC scheduling."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
os.environ['PATH']='/opt/homebrew/bin:'+os.environ.get('PATH','')
import brahe as bh
from omegaconf import OmegaConf
from main import setup_scenario
from common.utils import compute_contact_times,contactExclusion
from network_design.upstream import UpstreamContacts
from network_design.geography import Countries,Geography,Site
from network_design.evaluation import FixedRateLink,NetworkEvaluator
from network_design.score import ScoreOptimizer,SearchSettings

def check():
    out=ROOT/'local_runs/upstream_oct2026'
    cfg=OmegaConf.load(out/'.hydra/config.yaml')
    start,end,satellites=setup_scenario(cfg)
    result=json.loads((out/'results.json').read_text())
    sites=[Site(*s) for s in result['gs_list']]
    provider=UpstreamContacts(satellites,start,end,cfg.scenario.datarate)
    evaluator=NetworkEvaluator(provider,FixedRateLink(),180.000001)
    actual=evaluator(sites)*8e12
    expected=result['data_downlink']
    assert abs(actual-expected)/max(1,expected)<1e-7,(actual,expected)
    # Also exercise simultaneous contacts at multiple stations/satellites.
    comparison_sites=[Site(-105,40),Site(140,-30),Site(15,65)]
    contacts,_=compute_contact_times(satellites,[bh.PointLocation(s.longitude,s.latitude) for s in comparison_sites],start,end)
    _,seconds=contactExclusion(contacts,cfg)
    cbc=float(sum(seconds))*cfg.scenario.datarate
    highs=evaluator(comparison_sites)*8e12
    unlabelled_cbc=cbc
    # Explicit identities prevent different stations being grouped as location_id=None.
    locations=[bh.PointLocation(s.longitude,s.latitude).with_id(i) for i,s in enumerate(comparison_sites)]
    identified_contacts,_=compute_contact_times(satellites,locations,start,end)
    _,identified_seconds=contactExclusion(identified_contacts,cfg)
    cbc=float(sum(identified_seconds))*cfg.scenario.datarate
    assert abs(highs-cbc)/max(1,cbc)<1e-7,(highs,cbc)
    geography=Geography(Countries.read(ROOT/'data/countries/ne_110m_admin_0_countries.shp'),2,{'USA':1,'AUS':1},min_separation_km=300)
    design=ScoreOptimizer(evaluator,geography,SearchSettings(starts_per_move=1,evaluations_per_start=18,max_cycles=1)).solve()
    report={'upstream_bits':expected,'adapter_bits':actual,'multi_station_unlabelled_cbc_bits':unlabelled_cbc,'multi_station_cbc_bits':cbc,'multi_station_highs_bits':highs,'design':design,
            'scope':'Current upstream access engine and saved scenario; CBC/HiGHS evaluation agreement, not an optimizer ranking.'}
    (out/'adapter_check.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='design'},indent=2))
    return report
if __name__=='__main__':check()
