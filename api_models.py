"""Public response contracts; engine-specific details remain explicitly nested."""
from datetime import datetime
from typing import Any
from pydantic import BaseModel,ConfigDict

class CalculationResponse(BaseModel):
    model_config=ConfigDict(extra="allow")
    timestamp:datetime
    kp_score:float
    ruling_planets:dict[str,str]
    components:dict[str,Any]
    rows:list[dict[str,Any]]

class MatchRow(BaseModel):
    model_config=ConfigDict(extra="allow")
    timestamp:datetime
    score:float
    matched:int
    category:str
    reference:float|None=None
    price_5:float|None=None
    price_15:float|None=None
    price_30:float|None=None
    price_60:float|None=None
    source:str|None=None
    quality:str|None=None

class MatchResponse(BaseModel):
    total:int
    rows:list[MatchRow]

class Candle(BaseModel):
    timestamp:datetime
    open:float
    high:float
    low:float
    close:float

class CandleResponse(BaseModel):
    rows:list[Candle]
    convention:str
