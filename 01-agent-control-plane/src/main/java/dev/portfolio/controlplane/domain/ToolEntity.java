package dev.portfolio.controlplane.domain;

import jakarta.persistence.*;

@Entity
@Table(name="tools")
public class ToolEntity {
    @Id @GeneratedValue(strategy=GenerationType.IDENTITY)
    private Long id;
    @Column(unique=true, nullable=false) private String name;
    private String description;
    @Enumerated(EnumType.STRING) private Risk risk;

    protected ToolEntity() {}
    public ToolEntity(String name, String description, Risk risk) { this.name=name; this.description=description; this.risk=risk; }
    public Long getId(){return id;} public String getName(){return name;} public String getDescription(){return description;} public Risk getRisk(){return risk;}
}
