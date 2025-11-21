import mysql.connector
from mysql.connector import pooling
from .settings import EnvConfig

import logging


class Database:
    """Gerenciador de conexões MySQL com Pool automático."""

    __pool = None
    logger = logging.getLogger("uvicorn.info")

    @classmethod
    def init_pool(cls):
        """Inicializa o pool com configurações do .env."""
        if cls.__pool is None:
            cls.__pool = pooling.MySQLConnectionPool(
                pool_name="analysis_pool",
                pool_size=EnvConfig.DB_POOL_SIZE,
                pool_reset_session=True,
                host=EnvConfig.DB_HOST,
                port=EnvConfig.DB_PORT,
                user=EnvConfig.DB_USER,
                password=EnvConfig.DB_PASS,
                database=EnvConfig.DB_NAME
            )
            cls.logger.info("📌 Pool de conexões MySQL inicializado.")

    @classmethod
    def get_connection(cls):
        """Pega uma conexão do Pool (ou inicializa se preciso)."""
        if cls.__pool is None:
            cls.init_pool()
        return cls.__pool.get_connection()

    @classmethod
    def query(cls, sql: str, params=None, fetchone=False):
        """Executa SELECT, INSERT, UPDATE, DELETE com segurança."""
        conn = cls.get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(sql, params or [])

            if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
                conn.commit()
                return cursor.rowcount

            if fetchone:
                return cursor.fetchone()

            return cursor.fetchall()

        finally:
            cursor.close()
            conn.close()
