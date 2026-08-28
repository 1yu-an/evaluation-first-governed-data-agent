import unittest
from src.research import build_claim
class T(unittest.TestCase):
 def test_evidence(self):
  c=build_claim(); self.assertGreaterEqual(len(c.evidence),2); self.assertLess(c.confidence,1.0)
if __name__=='__main__':unittest.main()
