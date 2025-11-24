# api/main.py

import asyncio
import json
import os
import shutil
import uuid
from typing import Dict
from contextlib import asynccontextmanager  # <-- 1. Importar
import glob  # <-- 1. Importar

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import logging

from api.schemas.models import PTPCreate, PTPUpdate

from api.core.settings import EnvConfig
from api.core.database import Database
from api.core.excel_styler import autoajuste

from api.core.analysis import GeoAnalyzer
from api.core.models.ptp_model import PTPModel




# ==============================================================================
# --- Definição das Pastas de Trabalho ---
# ==============================================================================
UPLOADS_DIR = EnvConfig.UPLOADS_DIR
RESULTS_DIR = EnvConfig.RESULTS_DIR
KMZ_DIR = EnvConfig.KMZ_DIR

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# 2. Definir o dicionário que será populado no startup
analysis_results: Dict[str, str] = {}


# ==============================================================================
# --- 3. Função de Ciclo de Vida (Lifespan) ---
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configuração de Logger para mensagem no terminal
    logger = logging.getLogger("uvicorn.info")

    logger.info("")
    logger.info(f"# =============================================")
    logger.info(f"# ")
    logger.info(f"# Title: {EnvConfig.API_TITLE}")
    logger.info(f"# Description: {EnvConfig.API_DESCRIPTION}")
    logger.info(f"# Porta: {EnvConfig.API_PORT}")
    logger.info(f"# Version: {EnvConfig.API_VERSION}")
    logger.info(f"# ")
    logger.info(f"# =============================================")
    logger.info("")
    
    # --- CÓDIGO A SER EXECUTADO ANTES DO SERVIDOR INICIAR ---
    logger.info("Servidor iniciando... Populando cache de resultados existentes...")
    
    # Define o padrão de busca (ex: C:\..._geoespacial\API\results\resultado_*.xlsx)
    pattern = os.path.join(RESULTS_DIR, "resultado_*.xlsx")
    
    count = 0
    # Usa glob para encontrar todos os arquivos que correspondem ao padrão
    for full_path in glob.glob(pattern):
        try:
            filename = os.path.basename(full_path)
            
            # Extrai o result_id do nome do arquivo
            # "resultado_" tem 10 caracteres, ".xlsx" tem 5
            result_id = filename[10:-5]
            
            # Adiciona ao dicionário em memória
            analysis_results[result_id] = full_path
            count += 1
        except Exception as e:
            logger.error(f"Erro ao carregar o resultado '{filename}' no cache: {e}")
            
    logger.info(f"Cache populado com {count} resultados anteriores.")
    
    # O 'yield' é o ponto onde a aplicação FastAPI fica "rodando"
    yield
    
    # --- CÓDIGO A SER EXECUTADO QUANDO O SERVIDOR DESLIGAR (opcional) ---
    logger.warning("Servidor desligando...")


# ==============================================================================
# --- 4. Configuração da Aplicação ---
# ==============================================================================
app = FastAPI(
    title=EnvConfig.API_TITLE,
    description=EnvConfig.API_DESCRIPTION,
    version=EnvConfig.API_VERSION,
    lifespan=lifespan
)

# --- Configuração de CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=EnvConfig.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Iniciando o banco de dados ---
Database.init_pool()

# --- Validando Extenções permitidas ---
def is_allowed_extension(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in EnvConfig.ALLOWED_EXTENSIONS

# --- Endpoints da API ---

@app.post("/analyze/")
async def analyze_viability(
    raio_km: float = Form(0.0),
    coordenadas: str = Form(...),
    col_velocidade: str = Form('VELOCIDADE'),
    type_busca: int = Form(3),
    file: UploadFile = File(...)
):
    """
    Inicia uma análise de viabilidade.
    - **raio_km**: Raio de proximidade em quilômetros.
    - **file**: Arquivo .xlsx com os pontos para análise.
    
    Retorna um stream de Server-Sent Events (SSE) com o progresso.
    O último evento conterá o resumo e o ID para download do resultado.
    """
    
    # Verificando se arquivo é maior que tamanho estabelecido
    if file.size and file.size > EnvConfig.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(413, f"Arquivo excede o limite de {EnvConfig.MAX_UPLOAD_SIZE_BYTES // 1024 // 1024}MB")

    # Verificação da extensão
    if not is_allowed_extension(file.filename):
        allowed = ", ".join(EnvConfig.ALLOWED_EXTENSIONS)
        raise HTTPException(
            400,
            detail=f"Extensão não permitida. Permitidas: {allowed}"
        )
    
    # Salva o arquivo enviado temporariamente
    file_id = str(uuid.uuid4())
    upload_path = os.path.join(UPLOADS_DIR, f"{file_id}_{file.filename}")
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    async def event_stream_generator():
        analyzer = GeoAnalyzer(
            pasta_kmz=KMZ_DIR,
            arquivo_excel_path=upload_path,
            raio_km=raio_km,
            coluna_coordenadas=coordenadas,
            coluna_velocidade=col_velocidade,
            type_busca=type_busca
        )
        
        df_final, resumo = None, None
        
        # O gerador da classe de análise produz o progresso
        for progress, message in analyzer.run_analysis():
            if progress == -1: # Flag de erro
                error_event = {"status": "error", "message": message}
                yield f"data: {json.dumps(error_event)}\n\n"
                os.remove(upload_path)
                return

            event_data = {"progress": progress, "message": message}
            yield f"data: {json.dumps(event_data)}\n\n"
            await asyncio.sleep(0.1) # Pequeno delay para a UI respirar

            # Acessa o resultado final quando o gerador termina
            # df_final, resumo = analyzer.run_analysis().__closure__[0].cell_contents

            # --- CORREÇÃO APLICADA AQUI ---
            # Após o loop, pegamos os resultados que foram salvos na instância do analyzer
            df_final = analyzer.df_final
            resumo = analyzer.resumo
            # --- FIM DA CORREÇÃO ---

        if df_final is not None:
            # Salva o arquivo de resultado final
            result_id = str(uuid.uuid4())
            result_path = os.path.join(RESULTS_DIR, f"resultado_{result_id}.xlsx")
            df_final.to_excel(result_path, index=False, engine='openpyxl')
            analysis_results[result_id] = result_path

            
            # Aplicando Cores
            df_final.to_excel(result_path, index=False, engine='openpyxl')

            # Aplicar cores no arquivo Excel
            autoajuste(result_path)

            analysis_results[result_id] = result_path
            
            # Envia o evento final com o resumo e o ID de download
            final_event = {
                "status": "complete",
                "summary": resumo,
                "result_id": result_id
            }
            yield f"data: {json.dumps(final_event)}\n\n"
        
        # Limpa o arquivo de upload
        os.remove(upload_path)

    return StreamingResponse(event_stream_generator(), media_type="text/event-stream")


@app.get("/download/{result_id}")
async def download_result(result_id: str):
    """
    Baixa o arquivo Excel de resultado da análise.
    - **result_id**: O ID retornado pelo endpoint /analyze/ no evento final.
    """
    file_path = analysis_results.get(result_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Resultado não encontrado ou expirado.")
    
    return FileResponse(
        path=file_path,
        filename=os.path.basename(file_path),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    
@app.get("/delete/{result_id}")
async def delete_result(result_id: str):
    """
    Deletar o arquivo Excel de resultado da análise.
    - **result_id**: O ID retornado pelo endpoint /analyze/ no evento final.
    """
    file_path = analysis_results.get(result_id)
    
    async def event_delete():
        if not file_path or not os.path.exists(file_path):
            # Envia o evento final com o resumo e o ID de download
            result_delete = {
                "status": "error",
                "message": 'Arquivo não encontrado ou já foi removido.',
                "result_id": result_id
            }
            yield f"data: {json.dumps(result_delete)}\n\n"
        else:
            # Limpa o arquivo solicitado
            os.remove(file_path)
            # Envia o evento final com o resumo e o ID de download
            result_delete = {
                "status": "success",
                "message": 'Arquivo removido com sucesso.',
                "result_id": result_id
            }
            yield f"data: {json.dumps(result_delete)}\n\n"
        
    return StreamingResponse(event_delete(), media_type="text/event-stream")
    

@app.get("/ptp/find")
async def find_ptp(lat: float = Query(...), lon: float = Query(...), raio_km: float = Query(50.0)):
    """
    Busca a rede PTP mais próxima (retorna null se nada)
    GET /ptp/find?lat=...&lon=...&raio_km=50
    """
    try:
        row = PTPModel.rede_ptp(lat, lon, raio_km=raio_km)
        return {"ok": True, "data": row}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/ptp/list")
async def list_ptp(page: int = Query(1), limit: int = Query(50)):
    try:
        data = PTPModel.listar_paginado(page=page, limit=limit)
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    

   
@app.get("/ptp/municipios/search")
async def search_municipios(q: str = Query(..., min_length=3)):
    try:
        cidades = PTPModel.buscar_cidades(q)
        return {"ok": True, "data": cidades}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/ptp/create")
async def create_ptp(ptp: PTPCreate):
    try:
        PTPModel.criar(ptp.rede_ptp, ptp.codigo_ibge, ptp.codigo_uf)
        return {"ok": True, "msg": "Rede adicionada à cidade com sucesso!"}
    except ValueError as ve:
        return {"ok": False, "error": str(ve)} # Erro de duplicidade
    except Exception as e:
        return {"ok": False, "error": f"Erro interno: {str(e)}"}

@app.post("/ptp/update")
async def update_ptp(ptp: PTPUpdate):
    try:
        PTPModel.atualizar(ptp.id, ptp.rede_ptp)
        return {"ok": True, "msg": "Atualizado com sucesso"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/ptp/delete")
async def delete_ptp(id: int = Query(...)):
    try:
        PTPModel.deletar(id)
        return {"ok": True, "msg": "Deletado com sucesso"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
