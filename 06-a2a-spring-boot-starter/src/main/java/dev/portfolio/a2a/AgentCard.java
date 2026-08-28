package dev.portfolio.a2a;
import java.util.List;
public record AgentCard(String name,String description,String version,List<Skill> skills){public record Skill(String id,String name,String description){}}
