package dev.portfolio.controlplane.service;
import dev.portfolio.controlplane.domain.ToolEntity;
import dev.portfolio.controlplane.repo.ToolRepository;
import org.springframework.stereotype.Service;
import java.util.*;

@Service
public class ToolRouter {
    private final ToolRepository repo;
    public ToolRouter(ToolRepository repo){this.repo=repo;}

    public Optional<ToolEntity> route(String requestedTool, String intent){
        if(requestedTool!=null && !requestedTool.isBlank()) return repo.findByName(requestedTool);
        String q = intent == null ? "" : intent.toLowerCase(Locale.ROOT);
        // Simple baseline router. Replace with embedding/BM25 hybrid routing. / 简单基线，实践时替换为混合检索。
        return repo.findAll().stream().filter(t -> q.contains(t.getName().split("\\.")[0].toLowerCase(Locale.ROOT))).findFirst();
    }
}
