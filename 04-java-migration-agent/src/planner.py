def plan(info: dict) -> list[dict]:
    steps=[]
    if info.get('java_version') not in {'17','21'}:
        steps.append({'kind':'java-version','from':info.get('java_version'),'to':'21','risk':'MEDIUM'})
    if info.get('junit4'):
        steps.append({'kind':'junit','from':'4','to':'5','risk':'MEDIUM'})
    steps.append({'kind':'verify','command':'mvn test','risk':'LOW'})
    return steps
