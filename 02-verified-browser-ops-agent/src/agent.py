from .model import Task, StepResult, Status

class VerifiedAgent:
    def __init__(self, browser): self.browser=browser

    def execute(self, task: Task) -> StepResult:
        # Risk policy is deterministic. / 风险策略必须是确定性的。
        if task.action in {"delete", "pay", "transfer"}:
            return StepResult(Status.WAITING_APPROVAL, {}, "high-risk action / 高风险动作需审批")
        try:
            self.browser.act(task.action, task.target, task.value)
        except Exception as exc:
            return StepResult(Status.FAILED, {}, f"action failed: {exc}")
        return self.verify(task)

    def verify(self, task: Task) -> StepResult:
        if task.action == "set":
            actual=self.browser.observe(task.target)
            ok=actual==task.value
            return StepResult(Status.VERIFIED if ok else Status.FAILED,{task.target:actual},"state verified / 状态已验证" if ok else "state mismatch / 状态不匹配")
        if task.action == "send_invoice":
            key=f"order:{task.target}:invoice_sent"; actual=self.browser.observe(key)
            return StepResult(Status.VERIFIED if actual is True else Status.FAILED,{key:actual},"invoice verified / 发票状态已验证")
        if task.action == "open":
            actual=self.browser.observe("page")
            return StepResult(Status.VERIFIED if actual==task.target else Status.FAILED,{"page":actual},"page verified / 页面已验证")
        return StepResult(Status.FAILED,{},"no verifier / 缺少验证器")
