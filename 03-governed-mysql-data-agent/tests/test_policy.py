import unittest
from src.policy import validate_sql
class PolicyTest(unittest.TestCase):
 def test_select(self): self.assertTrue(validate_sql("SELECT * FROM orders")[0])
 def test_delete(self): self.assertFalse(validate_sql("DELETE FROM orders")[0])
 def test_multi(self): self.assertFalse(validate_sql("SELECT 1; DROP TABLE x")[0])
if __name__=='__main__': unittest.main()
