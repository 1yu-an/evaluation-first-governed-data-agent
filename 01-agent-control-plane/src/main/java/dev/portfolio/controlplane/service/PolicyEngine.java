package dev.portfolio.controlplane.service;
import dev.portfolio.controlplane.domain.*;
import org.springframework.stereotype.Service;

@Service
public class PolicyEngine {
    public PolicyDecision decide(String actor, ToolEntity tool) {
        // Deterministic policy before LLM/tool execution. / 在模型或工具执行前做确定性策略判断。
        if (tool.getName().contains("delete")) return PolicyDecision.deny("destructive tool / 破坏性工具");
        if (tool.getRisk() == Risk.HIGH) return PolicyDecision.approval("high risk / 高风险需审批");
        if ("guest".equalsIgnoreCase(actor) && tool.getRisk()!=Risk.LOW) return PolicyDecision.deny("guest role / 游客角色限制");
        return PolicyDecision.allow("policy passed / 策略通过");
    }
}
