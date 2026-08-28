import unittest
from src.browser import FakeBrowser
from src.agent import VerifiedAgent
from src.model import Task, Status

class AgentTest(unittest.TestCase):
    def test_state_is_verified(self):
        a=VerifiedAgent(FakeBrowser()); r=a.execute(Task("set","customer:42:plan","PRO")); self.assertEqual(Status.VERIFIED,r.status)
    def test_risky_action_waits(self):
        a=VerifiedAgent(FakeBrowser()); r=a.execute(Task("pay","invoice:9","5000")); self.assertEqual(Status.WAITING_APPROVAL,r.status)
if __name__=='__main__': unittest.main()
