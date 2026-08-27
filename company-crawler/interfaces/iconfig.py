from pydantic import BaseModel, Field, model_validator
from typing import List, Optional


class ICrawlerConfig(BaseModel):
    request_timeout: float = Field(default=30.0, gt=0)
    user_agent: str = Field(default="MyBot/1.0")
    proxy: Optional[str] = None
    headless: bool = True
    uc: bool = True


class IQuery(BaseModel):
    company_name: str = Field(default="")
    stock_ticket: str = Field(default="")

    @model_validator(mode="after")
    def check_at_least_one(self):
        values = [self.company_name, self.stock_ticket]
        if not any(v is not None and v != "" for v in values):
            raise ValueError("At least one field must be provided and non-empty.")
        return self
