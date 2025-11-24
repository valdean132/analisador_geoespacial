-- migrations/001_create_municipios.sql
-- Recomendado MySQL 8+
CREATE TABLE IF NOT EXISTS `municipios` (
  `codigo_ibge` INT NOT NULL PRIMARY KEY,
  `nome` VARCHAR(100) NOT NULL,
  `latitude` DOUBLE NOT NULL,
  `longitude` DOUBLE NOT NULL,
  `coordenada` POINT NOT NULL,
  `capital` TINYINT(1) NOT NULL,
  `codigo_uf` INT NOT NULL,
  `siafi_id` VARCHAR(4) NOT NULL,
  `ddd` INT NOT NULL,
  `fuso_horario` VARCHAR(32) NOT NULL,
  UNIQUE INDEX `siafi_id` (`siafi_id` ASC) VISIBLE,
  INDEX `codigo_uf` (`codigo_uf` ASC) VISIBLE,
  CONSTRAINT `municipios_ibfk_1`
    FOREIGN KEY (`codigo_uf`)
    REFERENCES `estados` (`codigo_uf`),
  SPATIAL INDEX spx_coordenada (coordenada))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;

-- Observação:
-- Ao inserir, use: INSERT INTO ptp_redes (rede_ptp, cidade, estado, uf, latitude, longitude, coordenada)
-- VALUES (..., ..., ..., ..., lat, lon, ST_SRID(POINT(lon, lat), 4326));
