# api/core/models/ptp_model.py
from typing import Optional, Dict
from api.core.database import Database

class PTPModel:
    """
    Modelo/DAO para operações relacionadas a redes PTP.
    Usa Database.query(sql, params, fetchone/fetchall).
    """

    @staticmethod
    def rede_ptp(lat: float, lon: float, raio_km: float = 50.0) -> Optional[Dict]:
        """
        Retorna a linha (dict) da rede mais próxima dentro do raio (km).
        Retorno: dict com colunas do DB (ex: rede_ptp, cidade, uf, distancia_km) ou None.
        OBS: ajuste o nome da tabela/colunas conforme sua modelagem.
        """
        # Query de exemplo otimizada com ST_Distance_Sphere (MySQL)
        # Ajuste 'ptp_redes' e colunas 'latitude'/'longitude' conforme sua tabela real.
        
        sql = """
            SELECT 
                -- Junta todas as redes encontradas, remove duplicatas e ordena alfabeticamente
                GROUP_CONCAT(DISTINCT rp.rede_ptp ORDER BY rp.rede_ptp ASC SEPARATOR ' / ') AS redes
            FROM 
                redes_ptp rp
            INNER JOIN (
                -- --- INÍCIO DA SUBQUERY: Acha as 5 cidades mais próximas ---
                SELECT DISTINCT 
                    c.codigo_ibge,
                    (ST_Distance_Sphere(POINT(c.longitude, c.latitude), POINT(%s, %s)) / 1000) AS dist_calc
                FROM 
                    redes_ptp sub_rp
                INNER JOIN 
                    municipios c ON sub_rp.codigo_ibge = c.codigo_ibge
                INNER JOIN 
                    estados e ON sub_rp.codigo_uf = e.codigo_uf
                WHERE 
                    ST_Distance_Sphere(POINT(c.longitude, c.latitude), POINT(%s, %s)) <= %s * 1000
                ORDER BY 
                    dist_calc ASC
                LIMIT 5
                -- --- FIM DA SUBQUERY ---
            ) AS top_5_locais ON rp.codigo_ibge = top_5_locais.codigo_ibge;
        """

        params = (lon, lat, lon, lat, float(raio_km))

        try:
            row = Database.query(sql, params=params, fetchone=True)
            return row  # None se não encontrado
        except Exception as e:
            # Log leve — preferível usar logger
            print("PTPModel.buscar_rede_mais_proxima error:", e)
            return None

    @staticmethod
    def listar_paginado(page: int = 1, limit: int = 50):
        offset = (page - 1) * limit
        sql = """
            SELECT
                rp.id,
                rp.rede_ptp AS redes,
                c.nome AS cidade, 
                e.uf, 
                c.latitude AS lat, 
                c.longitude AS lon
            FROM 
                redes_ptp rp 
            INNER JOIN 
                municipios c ON rp.codigo_ibge = c.codigo_ibge 
            INNER JOIN 
                estados e ON rp.codigo_uf = e.codigo_uf 
            ORDER BY 
                c.nome ASC
            LIMIT %s OFFSET %s;
        """
        rows = Database.query(sql, params=(limit, offset))
        total_row = Database.query("SELECT COUNT(1) AS total FROM redes_ptp;", fetchone=True)
        total = total_row["total"] if total_row else 0
        return {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
            "data": rows
        }
        
    @staticmethod
    def buscar_cidades(termo: str):
        """Busca cidades para o autocomplete (limitado a 10)"""
        sql = """
            SELECT c.codigo_ibge, c.nome, c.codigo_uf, e.uf
            FROM municipios c
            INNER JOIN 
                estados e ON c.codigo_uf = e.codigo_uf 
            WHERE c.nome LIKE %s 
            LIMIT 10
        """
        return Database.query(sql, params=(f"%{termo}%",))

    @staticmethod
    def criar(rede_ptp: str, codigo_ibge: int, codigo_uf: int):
        """
        Cria uma rede vinculada a uma cidade existente.
        Busca UF automaticamente da tabela municipios.
        Evita duplicidade.
        """
        
        # 1. Verifica se já existe essa rede nesta cidade
        check_sql = "SELECT id FROM redes_ptp WHERE rede_ptp = %s AND codigo_ibge = %s"
        existe = Database.query(check_sql, params=(rede_ptp, codigo_ibge), fetchone=True)
        
        if existe:
            raise ValueError(f"A rede '{rede_ptp}' já está cadastrada nesta cidade.")

        # 2. Insere buscando dados geográficos da tabela municipios
        # Nota: Assumindo que redes_ptp tem colunas: rede_ptp, codigo_ibge, codigo_uf
        sql = """
            INSERT INTO redes_ptp (rede_ptp, codigo_ibge, codigo_uf)
            VALUES (%s, %s, %s)
        """
        return Database.query(sql, params=(rede_ptp, codigo_ibge, codigo_uf))

    @staticmethod
    def atualizar(id: int, rede_ptp: str):
        sql = """
            UPDATE redes_ptp 
            SET rede_ptp = %s
            WHERE id = %s
        """
        return Database.query(sql, params=(rede_ptp, id))

    @staticmethod
    def deletar(id: int):
        sql = "DELETE FROM redes_ptp WHERE id = %s"
        return Database.query(sql, params=(id,))