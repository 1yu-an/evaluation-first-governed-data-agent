from typing import Dict, Any

class FakeBrowser:
    """Stateful environment / 有状态环境模拟器。"""
    def __init__(self):
        self.state: Dict[str, Any] = {
            "order:1001:invoice_sent": False,
            "customer:42:plan": "BASIC",
            "page": "dashboard",
        }

    def act(self, action: str, target: str, value=None) -> None:
        if action == "open": self.state["page"] = target
        elif action == "set": self.state[target] = value
        elif action == "send_invoice": self.state[f"order:{target}:invoice_sent"] = True
        else: raise ValueError(f"unknown action: {action}")

    def observe(self, key: str):
        return self.state.get(key)
