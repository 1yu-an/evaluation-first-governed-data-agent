package dev.portfolio.controlplane.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name="audit_logs")
public class AuditEntity {
    @Id @GeneratedValue(strategy=GenerationType.IDENTITY) private Long id;
    private Instant at;
    private String actor;
    private String toolName;
    private String decision;
    private String detail;
    protected AuditEntity() {}
    public AuditEntity(String actor,String toolName,String decision,String detail){this.at=Instant.now();this.actor=actor;this.toolName=toolName;this.decision=decision;this.detail=detail;}
    public Long getId(){return id;} public Instant getAt(){return at;} public String getActor(){return actor;} public String getToolName(){return toolName;} public String getDecision(){return decision;} public String getDetail(){return detail;}
}
