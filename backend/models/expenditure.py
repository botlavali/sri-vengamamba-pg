from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class Expenditure(BaseModel):
    productName: str = Field(..., min_length=2, max_length=100)
    price: float
    date: datetime
    notes: Optional[str] = ""