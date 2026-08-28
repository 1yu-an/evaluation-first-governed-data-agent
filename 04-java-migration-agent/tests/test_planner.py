import unittest
from src.planner import plan
class T(unittest.TestCase):
 def test_old_java(self): self.assertTrue(any(x['kind']=='java-version' for x in plan({'java_version':'8','junit4':False})))
if __name__=='__main__':unittest.main()
