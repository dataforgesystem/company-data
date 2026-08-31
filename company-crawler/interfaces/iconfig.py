from pydantic import BaseModel, Field, model_validator, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Dict, Any
from craft.utils.general_utils import GeneralUtils


class ICrawlerConfig(BaseModel):
    request_timeout: float = Field(default=30.0, gt=0)
    user_agent: str = Field(default_factory=GeneralUtils.get_random_user_agent)
    proxy: Optional[str] = None
    headless: bool = True
    uc: bool = True
    company_cache_expiry_time_days: int = Field(default=90)
    search_cache_expiry_time_days: int = Field(default=90)
    force_rescrape: bool = Field(
        default=False,
        description="When set to true, will always bypass cache and scrape the data. Recommended to keep it False",
    )


class IQuery(BaseModel):
    company_name: str = Field(default="")
    stock_ticket: str = Field(default="")

    @model_validator(mode="after")
    def check_at_least_one(self):
        values = [self.company_name, self.stock_ticket]
        if not any(v is not None and v != "" for v in values):
            raise ValueError("At least one field must be provided and non-empty.")
        return self
