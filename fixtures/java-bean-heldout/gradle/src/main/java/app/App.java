package app; import org.springframework.context.annotation.Bean; class App { @Bean Object one(){ return new Object(); } @Bean Object one(String s){ return s; } }
