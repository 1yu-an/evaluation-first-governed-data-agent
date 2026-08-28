package dev.portfolio.controlplane;
import dev.portfolio.controlplane.domain.*;
import dev.portfolio.controlplane.service.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PolicyEngineTest {
    @Test void highRiskRequiresApproval(){
        var p=new PolicyEngine();
        var d=p.decide("analyst",new ToolEntity("order.cancel","cancel",Risk.HIGH));
        assertEquals("REQUIRE_APPROVAL",d.action());
    }
    @Test void deleteIsDenied(){
        var p=new PolicyEngine();
        var d=p.decide("admin",new ToolEntity("customer.delete","delete",Risk.LOW));
        assertEquals("DENY",d.action());
    }
}
