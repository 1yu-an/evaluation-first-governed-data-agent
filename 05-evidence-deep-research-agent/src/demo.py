import json
from .research import build_claim
print(json.dumps(build_claim().to_dict(),ensure_ascii=False,indent=2))
