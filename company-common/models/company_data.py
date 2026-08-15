from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from enum import Enum
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_uid(company_domain: str) -> str:
    """Stable, idempotent id derived from domain - re-upserting the same
    company (e.g. after a re-scrape) naturally overwrites rather than dupes."""
    return company_domain.strip().lower()


class CompanyFundingInfo(BaseModel):
    funding_round: str = Field(..., description="The funding round of the company")
    funding_amount: float = Field(..., description="The funding amount of the company")
    funding_currency: str = Field(..., description="The currency of the funding amount")
    funding_date: Optional[str] = Field(default=None, description="The date of the funding round")
    investors: List[str] = Field(default_factory=list, description="List of investors in the funding round")


class CompanyOperatingMetrics(BaseModel):
    revenue: float = Field(..., description="The revenue of the company")
    profit: float = Field(..., description="The profit of the company")
    expenses: float = Field(..., description="The expenses of the company")
    growth_rate: float = Field(..., description="The growth rate of the company")
    market_share: float = Field(..., description="The market share of the company")


class CompanyStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ACQUIRED = "acquired"
    BANKRUPT = "bankrupt"
    CLOSED = "closed"


class CurrentCompanyStatus(BaseModel):
    status: CompanyStatus = Field(..., description="The status of the company")
    last_updated: Optional[datetime] = Field(default=None, description="The last updated date of the company status")


class CompanyEmployeeCount(BaseModel):
    total_employees: int = Field(..., description="The total number of employees")
    month: Optional[int] = Field(default=None, description="The month of the employee count")
    year: Optional[int] = Field(default=None, description="The year of the employee count")


class CompanyLocation(BaseModel):
    city: str = Field(..., description="The city of the company location")
    state: str = Field(..., description="The state of the company location")
    country: str = Field(..., description="The country of the company location")
    postal_code: str = Field(..., description="The postal code of the company location")


class CompanyData(BaseModel):
    uid: Optional[str] = Field(
        default=None, description="Stable id, auto-derived from company_domain if not set"
    )
    source: str = Field(..., description="Where this record came from, e.g. 'yahoo_finance', 'edgar'")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    company_name: str = Field(..., description="The name of the company")
    company_website: Optional[str] = Field(default=None, description="The website URL of the company")
    company_domain: str = Field(..., description="The domain of the company")
    company_industries: List[str] = Field(default_factory=list, description="The industries of the company")
    company_size: str = Field(..., description="The size of the company")
    company_founded_year: int = Field(..., description="The year the company was founded")
    company_website_url: Optional[str] = Field(default=None, description="The website URL of the company")
    company_funding_info: List[CompanyFundingInfo] = Field(default_factory=list, description="The funding information of the company")
    company_logo_url: Optional[str] = Field(default=None, description="The logo URL of the company")
    company_status: CurrentCompanyStatus = Field(
        default_factory=lambda: CurrentCompanyStatus(status=CompanyStatus.ACTIVE, last_updated=None),
        description="The status of the company",
    )
    company_description: Optional[str] = Field(default="", description="The description of the company")
    company_headquarters: Optional[str] = Field(default=None, description="The headquarters location of the company")
    company_ceo: Optional[str] = Field(default=None, description="The CEO of the company")
    company_type: Optional[str] = Field(default=None, description="The type of the company (e.g., private, public)")
    company_linkedin_url: Optional[str] = Field(default=None, description="The LinkedIn URL of the company")
    company_twitter_url: Optional[str] = Field(default=None, description="The Twitter URL of the company")
    company_symbol: Optional[str] = Field(default=None, description="The stock symbol of the company")
    company_operating_metrics: Optional[CompanyOperatingMetrics] = Field(default=None, description="The operating metrics of the company")
    company_employee_counts: List[CompanyEmployeeCount] = Field(default_factory=list, description="The employee counts of the company")
    company_locations: List[CompanyLocation] = Field(default_factory=list, description="The location information of the company")

    @model_validator(mode="after")
    def _fill_uid(self):
        if not self.uid:
            self.uid = make_uid(self.company_domain)
        return self