package dev.portfolio.controlplane.repo;
import dev.portfolio.controlplane.domain.AuditEntity;
import org.springframework.data.jpa.repository.JpaRepository;
public interface AuditRepository extends JpaRepository<AuditEntity,Long>{}
