package dev.portfolio.a2a;
import org.springframework.http.*;import org.springframework.web.bind.annotation.*;import java.util.*;
@RestController public class A2aController{
 private final TaskStore store; public A2aController(TaskStore store){this.store=store;}
 @GetMapping("/.well-known/agent-card.json") public AgentCard card(){return new AgentCard("order-agent","Demo Spring agent / Spring 示例 Agent","0.1",List.of(new AgentCard.Skill("echo","Echo","Echo a task / 回显任务")));}
 public record TaskRequest(String input){}
 @PostMapping("/a2a/tasks") public Map<String,Object> create(@RequestBody TaskRequest r){return store.create(r.input());}
 @GetMapping("/a2a/tasks/{id}") public ResponseEntity<Map<String,Object>> get(@PathVariable String id){var t=store.get(id);return t==null?ResponseEntity.notFound().build():ResponseEntity.ok(t);}
}
