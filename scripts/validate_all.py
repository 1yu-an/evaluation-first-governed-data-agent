#!/usr/bin/env python3
"""Repository validator / 仓库基础验证器。"""
from pathlib import Path
import ast
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []

for p in ROOT.rglob('*.py'):
    if '.venv' in p.parts:
        continue
    try:
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    except Exception as exc:
        errors.append(f'Python syntax: {p}: {exc}')

for p in ROOT.rglob('*.json'):
    try:
        json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc:
        errors.append(f'JSON: {p}: {exc}')

required = [
    '00-agent-eval-harness', '01-agent-control-plane',
    '02-verified-browser-ops-agent', '03-governed-mysql-data-agent',
    '04-java-migration-agent', '05-evidence-deep-research-agent',
    '06-a2a-spring-boot-starter'
]
for d in required:
    if not (ROOT/d).is_dir():
        errors.append(f'Missing directory: {d}')

if errors:
    print('\n'.join(errors))
    sys.exit(1)
print('OK: repository structure and parsable source files / 仓库结构与源文件基础检查通过')
