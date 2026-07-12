from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Expenditure(BaseModel):
    productName: str = Field(..., min_length=2, max_length=100)
    price: float
    date: datetime
    notes: Optional[str] = ""

class ExpenditureUpdate(BaseModel):
    productName: Optional[str] = None
    price: Optional[float] = None
    date: Optional[datetime] = None
    notes: Optional[str] = None