package dev.portfolio.controlplane.service;
public record PolicyDecision(String action, String reason) {
    public static PolicyDecision allow(String r){return new PolicyDecision("ALLOW",r);}
    public static PolicyDecision deny(String r){return new PolicyDecision("DENY",r);}
    public static PolicyDecision approval(String r){return new PolicyDecision("REQUIRE_APPROVAL",r);}
}
