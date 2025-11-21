import os
from dotenv import load_dotenv

load_dotenv()

class EnvConfig:
    """Carrega as variáveis de ambiente do .env de forma padronizada."""

    API_TITLE = os.getenv("API_TITLE", "API")
    API_DESCRIPTION = os.getenv("API_DESCRIPTION", "")
    API_VERSION = os.getenv("API_VERSION", "1.0.0")

    DEBUG = os.getenv("DEBUG", "false").lower() == "true"

    # Extensões permitidas
    RAW_EXTENSIONS = os.getenv("ALLOWED_EXTENSIONS", "xlsx")
    ALLOWED_EXTENSIONS = [ext.strip().lower() for ext in RAW_EXTENSIONS.split(",")]
    
    # CORS
    RAW_CORS = os.getenv("CORS_ORIGINS", "*")
    if RAW_CORS == "*":
        CORS_ORIGINS = ["*"]
    else:
        CORS_ORIGINS = [c.strip() for c in RAW_CORS.split(",")]

    # Diretórios
    API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    PROJECT_ROOT = os.path.dirname(API_DIR)

    UPLOADS_DIR = os.path.join(PROJECT_ROOT, os.getenv("UPLOADS_DIR", "uploads"))
    RESULTS_DIR = os.path.join(PROJECT_ROOT, os.getenv("RESULTS_DIR", "results"))
    KMZ_DIR = os.path.join(PROJECT_ROOT, os.getenv("KMZ_DIR", "kmzs"))

    # Limite de upload
    MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Servidor
    API_PORT = int(os.getenv("API_PORT", "8000"))

    # Banco de dados
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASS = os.getenv("DB_PASS", "")
    DB_NAME = os.getenv("DB_NAME", "")
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "280"))
