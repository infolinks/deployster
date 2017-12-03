CREATE SCHEMA testing
  CHARACTER SET utf8
  COLLATE utf8_bin;
USE testing;

CREATE TABLE `testing` (
  `id`   INT(11)                       NOT NULL AUTO_INCREMENT,
  `col1` VARCHAR(255) COLLATE utf8_bin NOT NULL,
  `col2` VARCHAR(255) COLLATE utf8_bin NOT NULL,
  PRIMARY KEY (`id`)
)
  ENGINE = InnoDB
  AUTO_INCREMENT = 1;
