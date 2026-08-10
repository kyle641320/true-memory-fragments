package heldout.cache;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.cache.annotation.CachePut;
import org.springframework.cache.annotation.CacheEvict;
class Service {
 @Cacheable(cacheNames={"heldout.users","heldout.profiles"}, key="#id", unless="#result == null") String get(String id){ return id; }
 @CachePut("heldout.users") String put(){ return "x"; }
 @CacheEvict("heldout.users") void evict(){}
}
