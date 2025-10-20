import asyncio
import json
import os
import shutil
import uuid
from typing import Dict

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
# --- 1. Importe o CORSMiddleware ---
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .core.analysis import GeoAnalyzer

# --- Configuração da Aplicação ---
app = FastAPI(
    title="Analisador de Viabilidade Geoespacial API",
    description="API para análise de viabilidade de pontos geoespaciais contra manchas de cobertura KMZ.",
    version="2.3.0"
)

# --- 2. Adicione o Middleware de CORS ---
# Esta é a parte mais importante. Ela deve vir logo após a criação do app.

# Define quais "origens" (bairros) podem acessar sua API.
# Usar ["*"] permite qualquer origem, o que é ótimo para desenvolvimento.
origins = [
    "*", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Permite as origens definidas acima
    allow_credentials=True, # Permite cookies (não usamos, mas é boa prática)
    allow_methods=["GET", "POST"],    # Permite todos os métodos (GET, POST, etc)
    allow_headers=["*"],    # Permite todos os cabeçalhos
)

# --- Pastas de Trabalho ---
# O diretório do arquivo main.py (ex: C:\..._geoespacial\API\api)
API_DIR = os.path.dirname(os.path.abspath(__file__))
# O diretório raiz do projeto (ex: C:\..._geoespacial\API)
PROJECT_ROOT = os.path.dirname(API_DIR)

# Agora, todos os caminhos são construídos a partir da raiz do projeto
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
KMZ_DIR = os.path.join(PROJECT_ROOT, "kmzs")

# Garante que as pastas necessárias existam
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# Armazenamento em memória para rastrear os resultados
analysis_results: Dict[str, str] = {}

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
    
    