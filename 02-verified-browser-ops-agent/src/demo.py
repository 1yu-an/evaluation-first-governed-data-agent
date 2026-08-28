from .browser import FakeBrowser
from .agent import VerifiedAgent
from .model import Task

b=FakeBrowser(); a=VerifiedAgent(b)
for t in [Task("open","orders"), Task("send_invoice","1001"), Task("set","customer:42:plan","PRO"), Task("pay","invoice:9","5000")]:
    print(t, "=>", a.execute(t))
