package heldout.ledger;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Update;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.SelectProvider;
@Mapper
public interface EntryMapper {
 @Select({"select payload", " from ledger_entry where id=#{id}"}) Object fetch(long id);
 @Insert("insert into ledger_entry(id) values(#{id})") int create(long id);
 @Update("update ledger_entry set payload=#{payload} where id=#{id}") int revise(long id, String payload);
 @Delete("delete from ledger_entry where id=#{id}") int erase(long id);
 @Select(DYNAMIC_SQL) Object dynamic(long id);
 @SelectProvider(type=Provider.class, method="sql") Object provider(long id);
 String DYNAMIC_SQL="select * from must_remain_opaque";
 class Provider { static String sql(){ return "select * from runtime_only"; } }
}
