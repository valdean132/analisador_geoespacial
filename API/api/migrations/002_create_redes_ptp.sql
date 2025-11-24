-- migrations/001_create_redes_ptp.sql
-- Recomendado MySQL 8+

CREATE TABLE IF NOT EXISTS `redes_ptp` (
  `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
  `codigo_ibge` INT NOT NULL,
  `codigo_uf` INT NOT NULL,
  `rede_ptp` VARCHAR(100) NOT NULL,
  INDEX `codigo_ibge` (`codigo_ibge` ASC) VISIBLE,
  CONSTRAINT `redes_ptp_ibfk_1`
    FOREIGN KEY (`codigo_ibge`)
    REFERENCES `municipios` (`codigo_ibge`),
  INDEX `codigo_uf` (`codigo_uf` ASC) VISIBLE,
  CONSTRAINT `redes_ptp_ibfk_2`
    FOREIGN KEY (`codigo_uf`)
    REFERENCES `estados` (`codigo_uf`),
  INDEX idx_rede_ptp (rede_ptp))
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_0900_ai_ci;

-- Observação:
-- Ao inserir, use: INSERT INTO ptp_redes (rede_ptp, cidade, estado, uf, latitude, longitude, coordenada)
-- VALUES (..., ..., ..., ..., lat, lon, ST_SRID(POINT(lon, lat), 4326));
