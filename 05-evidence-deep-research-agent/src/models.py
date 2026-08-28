from dataclasses import dataclass,asdict
@dataclass
class Evidence:
 source:str; text:str; supports:bool; timestamp:str
@dataclass
class Claim:
 text:str; evidence:list[Evidence]; confidence:float=0.0
 def to_dict(self): return {'text':self.text,'confidence':self.confidence,'evidence':[asdict(e) for e in self.evidence]}
