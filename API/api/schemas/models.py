from pydantic import BaseModel
from typing import Dict

class AnalysisSummary(BaseModel):
    total_pontos: int
    resumo_status: Dict[str, int]
    
class PTPCreate(BaseModel):
    rede_ptp: str
    codigo_ibge: int
    codigo_uf: int

class PTPUpdate(BaseModel):
    id: int
    rede_ptp: str