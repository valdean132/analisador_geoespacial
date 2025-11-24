-- Busca redes cadastradas

SELECT 
    -- Aqui já temos todas as redes agrupadas
    -- GROUP_CONCAT(DISTINCT rp.rede_ptp ORDER BY rp.rede_ptp ASC SEPARATOR ' / ') AS redes,
    rp.rede_ptp AS redes,
    c.nome AS cidade, 
    e.uf, 
    c.latitude AS lat, 
    c.longitude AS lon, 
    ROUND(ST_Distance_Sphere(POINT(c.longitude, c.latitude), POINT(-49.33150383423551, -16.683054550065705)) / 1000, 2) AS distancia_km 
FROM 
    redes_ptp rp 
INNER JOIN 
    municipios c ON rp.codigo_ibge = c.codigo_ibge 
INNER JOIN 
    estados e ON rp.codigo_uf = e.codigo_uf 
WHERE 
    ST_Distance_Sphere(POINT(c.longitude, c.latitude), POINT(-49.33150383423551, -16.683054550065705)) <= 50.0 * 1000 

ORDER BY 
    distancia_km ASC 
LIMIT 5;

-- ###

-- Busca Redes concatenando

SELECT 
    -- Aqui já temos todas as redes agrupadas
    GROUP_CONCAT(DISTINCT rp.rede_ptp ORDER BY rp.rede_ptp ASC SEPARATOR ' / ') AS redes,
    c.nome AS cidade, 
    e.uf, 
    c.latitude AS lat, 
    c.longitude AS lon, 
    ROUND(ST_Distance_Sphere(POINT(c.longitude, c.latitude), POINT(-49.33150383423551, -16.683054550065705)) / 1000, 2) AS distancia_km 
FROM 
    redes_ptp rp 
INNER JOIN 
    municipios c ON rp.codigo_ibge = c.codigo_ibge 
INNER JOIN 
    estados e ON rp.codigo_uf = e.codigo_uf 
WHERE 
    ST_Distance_Sphere(POINT(c.longitude, c.latitude), POINT(-49.33150383423551, -16.683054550065705)) <= 50.0 * 1000 
GROUP BY 
    c.codigo_ibge, c.nome, e.uf, c.latitude, c.longitude 
ORDER BY 
    distancia_km ASC 
LIMIT 5;

-- ###

-- Seleciona as redes encontradas

SELECT 
    -- Junta todas as redes encontradas, remove duplicatas e ordena alfabeticamente
    GROUP_CONCAT(DISTINCT rp.rede_ptp ORDER BY rp.rede_ptp ASC SEPARATOR ' / ') AS redes
FROM 
    redes_ptp rp
INNER JOIN (
    -- --- INÍCIO DA SUBQUERY: Acha as 5 cidades mais próximas ---
    SELECT DISTINCT 
        c.codigo_ibge,
        (ST_Distance_Sphere(POINT(c.longitude, c.latitude), POINT(-49.33150383423551, -16.683054550065705)) / 1000) AS dist_calc
    FROM 
        redes_ptp sub_rp
    INNER JOIN 
        municipios c ON sub_rp.codigo_ibge = c.codigo_ibge
    INNER JOIN 
        estados e ON sub_rp.codigo_uf = e.codigo_uf
    WHERE 
        ST_Distance_Sphere(POINT(c.longitude, c.latitude), POINT(-49.33150383423551, -16.683054550065705)) <= 50.0 * 1000
    ORDER BY 
        dist_calc ASC
    LIMIT 5
    -- --- FIM DA SUBQUERY ---
) AS top_5_locais ON rp.codigo_ibge = top_5_locais.codigo_ibge;