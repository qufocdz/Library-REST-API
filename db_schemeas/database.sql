-- MySQL Workbench Forward Engineering

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema librarydb
-- -----------------------------------------------------
DROP SCHEMA IF EXISTS `librarydb` ;

-- -----------------------------------------------------
-- Schema librarydb
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `librarydb` DEFAULT CHARACTER SET utf8 ;
USE `librarydb` ;

-- -----------------------------------------------------
-- Table `librarydb`.`author`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`author` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`author` (
  `author_id` INT NOT NULL AUTO_INCREMENT,
  `first_name` VARCHAR(45) NOT NULL,
  `last_name` VARCHAR(45) NOT NULL,
  PRIMARY KEY (`author_id`))
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`publisher`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`publisher` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`publisher` (
  `publisher_id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(45) NOT NULL,
  PRIMARY KEY (`publisher_id`))
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`category`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`category` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`category` (
  `category_id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(45) NOT NULL,
  PRIMARY KEY (`category_id`),
  UNIQUE INDEX `name_UNIQUE` (`name` ASC) VISIBLE)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`book`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`book` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`book` (
  `book_id` INT NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(45) NOT NULL,
  `publication_year` INT NOT NULL,
  `pages` INT NULL,
  `isbn` VARCHAR(20) NOT NULL,
  `rental_rate` DECIMAL(10,2) NOT NULL,
  `publisher_id` INT NOT NULL,
  PRIMARY KEY (`book_id`),
  INDEX `publisher_id_idx` (`publisher_id` ASC) VISIBLE,
  UNIQUE INDEX `isbn_UNIQUE` (`isbn` ASC) VISIBLE,
  CONSTRAINT `publisher_id`
    FOREIGN KEY (`publisher_id`)
    REFERENCES `librarydb`.`publisher` (`publisher_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`book_author`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`book_author` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`book_author` (
  `book_id` INT NOT NULL,
  `author_id` INT NOT NULL,
  PRIMARY KEY (`book_id`, `author_id`),
  INDEX `author_id_idx` (`author_id` ASC) VISIBLE,
  CONSTRAINT `book_id`
    FOREIGN KEY (`book_id`)
    REFERENCES `librarydb`.`book` (`book_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `author_id`
    FOREIGN KEY (`author_id`)
    REFERENCES `librarydb`.`author` (`author_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`address`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`address` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`address` (
  `address_id` INT NOT NULL,
  `district` VARCHAR(45) NOT NULL,
  `location` VARCHAR(45) NOT NULL,
  `postal_code` VARCHAR(45) NOT NULL,
  `street` VARCHAR(45) NOT NULL,
  `house_number` INT NOT NULL,
  PRIMARY KEY (`address_id`))
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`library`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`library` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`library` (
  `library_id` INT NOT NULL,
  `name` VARCHAR(45) NOT NULL,
  `address_id` INT NOT NULL,
  PRIMARY KEY (`library_id`),
  INDEX `fk_library_address1_idx` (`address_id` ASC) VISIBLE,
  CONSTRAINT `fk_library_address1`
    FOREIGN KEY (`address_id`)
    REFERENCES `librarydb`.`address` (`address_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`copy`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`copy` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`copy` (
  `copy_id` INT NOT NULL AUTO_INCREMENT,
  `status` ENUM('available', 'borrowed', 'lost', 'damaged') NOT NULL DEFAULT 'available',
  `book_id` INT NOT NULL,
  `library_id` INT NOT NULL,
  PRIMARY KEY (`copy_id`),
  INDEX `fk_copy_library1_idx` (`library_id` ASC) VISIBLE,
  INDEX `fk_copy_book1_idx` (`book_id` ASC) VISIBLE,
  CONSTRAINT `fk_copy_library1`
    FOREIGN KEY (`library_id`)
    REFERENCES `librarydb`.`library` (`library_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_copy_book1`
    FOREIGN KEY (`book_id`)
    REFERENCES `librarydb`.`book` (`book_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`reader_type`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`reader_type` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`reader_type` (
  `type_id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(45) NOT NULL,
  `max_books` INT NOT NULL,
  `borrow_days` INT NOT NULL,
  `fine_per_day` DECIMAL(5,2) NOT NULL,
  PRIMARY KEY (`type_id`))
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`reader`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`reader` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`reader` (
  `reader_id` INT NOT NULL AUTO_INCREMENT,
  `first_name` VARCHAR(45) NOT NULL,
  `last_name` VARCHAR(45) NOT NULL,
  `email` VARCHAR(45) NOT NULL,
  `phone` INT NOT NULL,
  `type_id` INT NOT NULL,
  `address_id` INT NOT NULL,
  PRIMARY KEY (`reader_id`),
  INDEX `type_id_idx` (`type_id` ASC) VISIBLE,
  INDEX `fk_reader_address1_idx` (`address_id` ASC) VISIBLE,
  CONSTRAINT `type_id`
    FOREIGN KEY (`type_id`)
    REFERENCES `librarydb`.`reader_type` (`type_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_reader_address1`
    FOREIGN KEY (`address_id`)
    REFERENCES `librarydb`.`address` (`address_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`library_card`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`library_card` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`library_card` (
  `card_id` INT NOT NULL AUTO_INCREMENT,
  `status` ENUM('active', 'suspended', 'blocked') NOT NULL DEFAULT 'active',
  `created_at` DATE NOT NULL,
  `reader_id` INT NOT NULL,
  PRIMARY KEY (`card_id`),
  INDEX `reader_id_idx` (`reader_id` ASC) VISIBLE,
  CONSTRAINT `reader_id`
    FOREIGN KEY (`reader_id`)
    REFERENCES `librarydb`.`reader` (`reader_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`rental`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`rental` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`rental` (
  `rental_id` INT NOT NULL AUTO_INCREMENT,
  `status` ENUM('active', 'overdue', 'returned', 'cancelled', 'lost', 'damaged') NULL,
  `rental_rate` INT NOT NULL COMMENT 'Field will store value of rental rate of book in particular rent. This allow us to store rental rate in rentals even after changing the current rental rate in book table\n',
  `rental_date` DATE NOT NULL,
  `due_date` DATE NOT NULL,
  `return_date` DATE NULL,
  `copy_id` INT NOT NULL,
  `card_id` INT NOT NULL,
  PRIMARY KEY (`rental_id`),
  INDEX `copy_id_idx` (`copy_id` ASC) VISIBLE,
  INDEX `card_id_idx` (`card_id` ASC) VISIBLE,
  CONSTRAINT `copy_id`
    FOREIGN KEY (`copy_id`)
    REFERENCES `librarydb`.`copy` (`copy_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `card_id`
    FOREIGN KEY (`card_id`)
    REFERENCES `librarydb`.`library_card` (`card_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`fine`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`fine` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`fine` (
  `fine_id` INT NOT NULL AUTO_INCREMENT,
  `amount` DECIMAL(10,2) NOT NULL,
  `note` TEXT NULL,
  `paid` TINYINT NOT NULL DEFAULT 0,
  `rental_id` INT NOT NULL,
  PRIMARY KEY (`fine_id`),
  INDEX `borrow_id_idx` (`rental_id` ASC) VISIBLE,
  CONSTRAINT `borrow_id`
    FOREIGN KEY (`rental_id`)
    REFERENCES `librarydb`.`rental` (`rental_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`payment`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`payment` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`payment` (
  `payment_id` INT NOT NULL AUTO_INCREMENT,
  `amount` DOUBLE NOT NULL COMMENT 'Sum o rental cost and eventual fine\n',
  `payment_date` DATE NULL,
  `rental_id` INT NOT NULL,
  PRIMARY KEY (`payment_id`),
  INDEX `fk_payment_rental1_idx` (`rental_id` ASC) VISIBLE,
  CONSTRAINT `fk_payment_rental1`
    FOREIGN KEY (`rental_id`)
    REFERENCES `librarydb`.`rental` (`rental_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`logs`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`logs` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`logs` (
  `log_id` INT NOT NULL AUTO_INCREMENT,
  `operation` VARCHAR(200) NULL,
  `log_date` DATE NULL,
  `details` TEXT NULL,
  PRIMARY KEY (`log_id`))
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`book_category`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`book_category` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`book_category` (
  `category_id` INT NOT NULL,
  `book_id` INT NOT NULL,
  PRIMARY KEY (`category_id`, `book_id`),
  INDEX `fk_book_has_category_category1_idx` (`category_id` ASC) VISIBLE,
  INDEX `fk_book_category_book1_idx` (`book_id` ASC) VISIBLE,
  CONSTRAINT `fk_book_has_category_category1`
    FOREIGN KEY (`category_id`)
    REFERENCES `librarydb`.`category` (`category_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_book_category_book1`
    FOREIGN KEY (`book_id`)
    REFERENCES `librarydb`.`book` (`book_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`internal_rental`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`internal_rental` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`internal_rental` (
  `internal_rental_id` VARCHAR(45) NOT NULL,
  `status` ENUM('requested', 'approved', 'rejected', 'shipped', 'received', 'active', 'returned_to_library', 'completed', 'cancelled') NOT NULL,
  `rental_id` INT NOT NULL,
  `source_library` INT NOT NULL,
  `target_library` INT NOT NULL,
  INDEX `fk_intern_rental_library1_idx` (`source_library` ASC) VISIBLE,
  INDEX `fk_intern_rental_library2_idx` (`target_library` ASC) VISIBLE,
  PRIMARY KEY (`internal_rental_id`),
  CONSTRAINT `fk_intern_rental_rental1`
    FOREIGN KEY (`rental_id`)
    REFERENCES `librarydb`.`rental` (`rental_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_intern_rental_library1`
    FOREIGN KEY (`source_library`)
    REFERENCES `librarydb`.`library` (`library_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION,
  CONSTRAINT `fk_intern_rental_library2`
    FOREIGN KEY (`target_library`)
    REFERENCES `librarydb`.`library` (`library_id`)
    ON DELETE NO ACTION
    ON UPDATE NO ACTION)
ENGINE = InnoDB;


-- -----------------------------------------------------
-- Table `librarydb`.`table1`
-- -----------------------------------------------------
DROP TABLE IF EXISTS `librarydb`.`table1` ;

CREATE TABLE IF NOT EXISTS `librarydb`.`table1` (
)
ENGINE = InnoDB;


SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
