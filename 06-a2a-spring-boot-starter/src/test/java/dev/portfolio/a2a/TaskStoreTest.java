package dev.portfolio.a2a;import org.junit.jupiter.api.Test;import static org.junit.jupiter.api.Assertions.*;
class TaskStoreTest{@Test void taskRoundTrip(){var s=new TaskStore();var t=s.create("hello");assertEquals("COMPLETED",s.get((String)t.get("id")).get("status"));}}
