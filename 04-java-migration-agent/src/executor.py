from pathlib import Path

def apply(repo: Path, steps: list[dict], dry_run=True) -> list[str]:
    actions=[]; pom=repo/'pom.xml'; text=pom.read_text(encoding='utf-8')
    for s in steps:
        if s['kind']=='java-version':
            actions.append(f"Java {s['from']} -> {s['to']}")
            if not dry_run: text=text.replace(f"<maven.compiler.source>{s['from']}</maven.compiler.source>","<maven.compiler.source>21</maven.compiler.source>").replace(f"<maven.compiler.target>{s['from']}</maven.compiler.target>","<maven.compiler.target>21</maven.compiler.target>")
        elif s['kind']=='junit': actions.append('JUnit 4 -> JUnit 5 requires dependency + source rewrite / 需要依赖与源码迁移')
        elif s['kind']=='verify': actions.append('VERIFY: '+s['command'])
    if not dry_run: pom.write_text(text,encoding='utf-8')
    return actions
