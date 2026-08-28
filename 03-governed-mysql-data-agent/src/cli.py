import json,sys
from .agent import DataAgent
print(json.dumps(DataAgent().answer(" ".join(sys.argv[1:]) or "revenue"),ensure_ascii=False,indent=2))
