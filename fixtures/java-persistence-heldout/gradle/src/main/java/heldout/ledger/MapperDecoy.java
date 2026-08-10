package heldout.ledger;
import fake.mybatis.Mapper;
import fake.mybatis.Select;
@Mapper interface MapperDecoy { @Select("select * from fabricated") Object nope(); }
