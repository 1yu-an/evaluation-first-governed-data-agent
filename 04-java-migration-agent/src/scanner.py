from pathlib import Path
import re

def inspect(repo: Path) -> dict:
    pom=(repo/'pom.xml').read_text(encoding='utf-8')
    java=re.search(r'<maven.compiler.source>([^<]+)</maven.compiler.source>',pom)
    junit4='junit:junit' in pom or '<artifactId>junit</artifactId>' in pom
    return {'java_version': java.group(1) if java else 'unknown','junit4':junit4,'has_pom':True}
