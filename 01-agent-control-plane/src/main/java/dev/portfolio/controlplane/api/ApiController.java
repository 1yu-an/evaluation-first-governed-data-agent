package dev.portfolio.controlplane.api;

import dev.portfolio.controlplane.domain.*;
import dev.portfolio.controlplane.repo.*;
import dev.portfolio.controlplane.service.*;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController
@RequestMapping("/api")
public class ApiController {
    private final ToolRepository tools; private final AuditRepository audits; private final ToolRouter router; private final PolicyEngine policy;
    public ApiController(ToolRepository tools, AuditRepository audits, ToolRouter router, PolicyEngine policy){this.tools=tools;this.audits=audits;this.router=router;this.policy=policy;}

    public record RegisterTool(String name,String description,Risk risk){}
    public record ExecuteRequest(String actor,String intent,String requestedTool){}

    @PostMapping("/tools/register")
    public ToolEntity register(@RequestBody RegisterTool r){return tools.save(new ToolEntity(r.name(),r.description(),r.risk()==null?Risk.LOW:r.risk()));}

    @GetMapping("/tools") public List<ToolEntity> list(){return tools.findAll();}

    @PostMapping("/execute")
    public ResponseEntity<Map<String,Object>> execute(@RequestBody ExecuteRequest r){
        ToolEntity tool=router.route(r.requestedTool(),r.intent()).orElse(null);
        if(tool==null) return ResponseEntity.badRequest().body(Map.of("status","NO_TOOL"));
        PolicyDecision d=policy.decide(r.actor()==null?"guest":r.actor(),tool);
        audits.save(new AuditEntity(r.actor(),tool.getName(),d.action(),d.reason()));
        if(!"ALLOW".equals(d.action())) return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("status",d.action(),"reason",d.reason(),"tool",tool.getName()));
        // Tool execution is intentionally adapter-based. / 工具执行刻意保留为适配器层，方便接 MCP/HTTP/DB。
        return ResponseEntity.ok(Map.of("status","EXECUTED","tool",tool.getName(),"verified",true,"result","mock-success"));
    }

    @GetMapping("/audit") public List<AuditEntity> audit(){return audits.findAll();}
}
