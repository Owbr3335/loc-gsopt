"""Check saved networks with finer contact detection and RF integration."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from network_design.orbits import Orbit,OrbitContacts
from network_design.geography import Site
from network_design.evaluation import NetworkEvaluator,FixedRateLink
from network_design.links import RFLink,RFSettings
reports=[]
for directory in sorted((ROOT/'local_runs/design').iterdir()):
    if not directory.is_dir():continue
    config=json.loads((directory/'config.json').read_text()); result=json.loads((directory/'result.json').read_text())
    settings=dict(config['propagation'],step_s=15)
    provider=OrbitContacts([Orbit(**o) for o in config['orbits']],**settings)
    lc=config['link'];link=FixedRateLink() if lc['type']=='fixed' else RFLink(provider,RFSettings(**dict(lc['settings'],integration_step_s=5)))
    actual=NetworkEvaluator(provider,link,config['minimum_contact_s'])([Site(**s) for s in result['sites']])
    error=abs(actual-result['objective'])/max(1e-12,result['objective'])
    reports.append({'scenario':directory.name,'saved_TB':result['objective'],'finer_TB':actual,'relative_difference':error})
    assert error<.005,(directory,error)
(ROOT/'local_runs/design/resolution_check.json').write_text(json.dumps(reports,indent=2)+'\n')
print(json.dumps(reports,indent=2))
