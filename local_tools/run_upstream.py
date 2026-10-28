"""Run the unchanged October 2026 upstream entry point, with local outputs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sites',type=int,default=1)
    p.add_argument('--passes',type=int,default=2,help='One selection pass plus refinement passes')
    p.add_argument('--output',type=Path,default=ROOT/'local_runs/upstream_oct2026')
    args=p.parse_args()
    if args.sites<1 or args.passes<1:p.error('sites and passes must be positive')
    env=dict(os.environ,WANDB_MODE='disabled')
    env.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
    env['PATH']='/opt/homebrew/bin:'+env.get('PATH','')
    subprocess.run([sys.executable,str(ROOT/'src/main.py'),'problem.method=nelder_ccgs',
                    f'problem.gs_num={args.sites}','problem.sat_num=2','end_epoch.day=2',
                    f'experiments.ccgs={args.passes}','debug.verbose=false','debug.plot=false',
                    'debug.wandb=false','debug.txtUpdate=false',f'hydra.run.dir={args.output.resolve()}'],
                   cwd=ROOT,env=env,check=True)
    metadata={'upstream_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'scope':'Unmodified upstream SCORE; one day, two Capella satellites; see .hydra/config.yaml',
              'placement_passes':args.passes,'station_count':args.sites}
    (args.output.resolve()/'baseline.json').write_text(json.dumps(metadata,indent=2)+'\n')
