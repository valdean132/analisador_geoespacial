# api/main.py

import asyncio
import json
import os
import shutil
import uuid
from typing import Dict
from contextlib import asynccontextmanager  # <-- 1. Importar
import glob  # <-- 1. Importar

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .core.analysis import GeoAnalyzer

# ==============================================================================
# --- Definição das Pastas de Trabalho ---
# ==============================================================================
API_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(API_DIR)

UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
KMZ_DIR = os.path.join(PROJECT_ROOT, "kmzs")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# 2. Definir o dicionário que será populado no startup
analysis_results: Dict[str, str] = {}

# ==============================================================================
# --- 3. Função de Ciclo de Vida (Lifespan) ---
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- CÓDIGO A SER EXECUTADO ANTES DO SERVIDOR INICIAR ---
    print("Servidor iniciando... Populando cache de resultados existentes...")
    
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
            print(f"Erro ao carregar o resultado '{filename}' no cache: {e}")
            
    print(f"Cache populado com {count} resultados anteriores.")
    
    # O 'yield' é o ponto onde a aplicação FastAPI fica "rodando"
    yield
    
    # --- CÓDIGO A SER EXECUTADO QUANDO O SERVIDOR DESLIGAR (opcional) ---
    print("Servidor desligando...")


# ==============================================================================
# --- 4. Configuração da Aplicação ---
# ==============================================================================
app = FastAPI(
    title="Analisador de Viabilidade Geoespacial API",
    description="API para análise de viabilidade...",
    version="2.4.0",
    lifespan=lifespan  # <-- 4. Informa ao FastAPI para usar nossa função
)

# --- Configuração de CORS ---
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints da API ---

@app.post("/analyze/")
async def analyze_viability(
    raio_km: float = Form(0.0),
    coordenadas: str = Form(...),
    col_velocidade: str = Form('VELOCIDADE'),
    file: UploadFile = File(...)
):
    """
    Inicia uma análise de viabilidade.
    - **raio_km**: Raio de proximidade em quilômetros.
    - **file**: Arquivo .xlsx com os pontos para análise.
    
    Retorna um stream de Server-Sent Events (SSE) com o progresso.
    O último evento conterá o resumo e o ID para download do resultado.
    """
    
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
            coluna_velocidade=col_velocidade
        )
        
        df_final, resumo = None, None
        
        # O gerador da classe de análise produz o progresso
        for progress, message in analyzer.run_analysis():
            if progress == -1: # Flag de erro
                error_event = {"status": "error", "message": message}
                yield f"data: {json.dumps(error_event)}\n\n"
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
    
    