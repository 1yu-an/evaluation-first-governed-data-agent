package dev.portfolio.a2a;
import org.springframework.stereotype.Component;import java.util.*;import java.util.concurrent.ConcurrentHashMap;
@Component public class TaskStore{
 private final Map<String,Map<String,Object>> tasks=new ConcurrentHashMap<>();
 public Map<String,Object> create(String input){String id=UUID.randomUUID().toString();var t=new LinkedHashMap<String,Object>();t.put("id",id);t.put("status","COMPLETED");t.put("input",input);t.put("output","echo: "+input);tasks.put(id,t);return t;}
 public Map<String,Object> get(String id){return tasks.get(id);}
}
