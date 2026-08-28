import argparse,json
from pathlib import Path
from .scanner import inspect
from .planner import plan
from .executor import apply
p=argparse.ArgumentParser();p.add_argument('repo');p.add_argument('--dry-run',action='store_true');a=p.parse_args()
repo=Path(a.repo); info=inspect(repo); steps=plan(info); print(json.dumps({'inspection':info,'plan':steps,'actions':apply(repo,steps,a.dry_run)},indent=2))
