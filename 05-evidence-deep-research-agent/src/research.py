from .models import Claim,Evidence

CORPUS=[
 {'source':'engineering-blog-A','timestamp':'2026-05-01','text':'Project Atlas reduced median latency by 30 percent after caching.'},
 {'source':'benchmark-B','timestamp':'2026-05-10','text':'Project Atlas latency improved by about 28 percent in our benchmark.'},
 {'source':'forum-C','timestamp':'2026-04-15','text':'Project Atlas showed no meaningful latency improvement in an older build.'},
]

def search(term:str): return [x for x in CORPUS if term.lower() in x['text'].lower()]

def build_claim(term='Project Atlas') -> Claim:
 rows=search(term); ev=[]
 for r in rows:
  lower=r['text'].lower(); supports=('improved' in lower or 'reduced' in lower)
  ev.append(Evidence(r['source'],r['text'],supports,r['timestamp']))
 pos=sum(e.supports for e in ev); neg=len(ev)-pos
 # Confidence rewards independent support but penalizes contradictions. / 多源支持提高置信度，冲突降低置信度。
 conf=max(0.0,min(1.0,(pos/(len(ev) or 1))-(0.15 if neg else 0)))
 return Claim(f'{term} improved latency',ev,round(conf,2))
