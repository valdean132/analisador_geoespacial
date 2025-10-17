from pydantic import BaseModel
from typing import Dict

class AnalysisSummary(BaseModel):
    total_pontos: int
    resumo_status: Dict[str, int]