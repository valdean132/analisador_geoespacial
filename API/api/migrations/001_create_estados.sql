-- migrations/001_create_estados.sql
-- Recomendado MySQL 8+
CREATE TABLE `estados` (
  `codigo_uf` INT NOT NULL,
  `uf` VARCHAR(2) NOT NULL,
  `nome` VARCHAR(100) NOT NULL,
  `latitude` FLOAT NOT NULL,
  `longitude` FLOAT NOT NULL,
  `regiao` VARCHAR(12) NOT NULL,
  PRIMARY KEY (`codigo_uf`))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;

-- Observação:
-- Ao inserir, use: INSERT INTO ptp_redes (rede_ptp, cidade, estado, uf, latitude, longitude, coordenada)
-- VALUES (..., ..., ..., ..., lat, lon, ST_SRID(POINT(lon, lat), 4326));
