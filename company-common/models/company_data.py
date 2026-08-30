from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime


class CompanyFundingInfo(BaseModel):
    funding_round: str = Field(..., description="The funding round of the company")
    funding_amount: float = Field(..., description="The funding amount of the company")
    funding_currency: str = Field(..., description="The currency of the funding amount")
    funding_date: Optional[str] = Field(
        default=None, description="The date of the funding round"
    )
    investors: List[str] = Field(
        default_factory=list, description="List of investors in the funding round"
    )


class CompanyOperatingMetric(BaseModel):
    company_specific_kpi: str = Field(..., description="Company Specific KPIs")
    metric_value: Optional[float] = Field(
        ..., description="Metric value of the defined KPIs"
    )
    unit_type: Optional[str] = Field(..., description="Unit type of the KPIs")
    date: Optional[datetime] = Field(..., description="date")


class CompanyStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ACQUIRED = "acquired"
    BANKRUPT = "bankrupt"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class CurrentCompanyStatus(BaseModel):
    status: CompanyStatus = Field(..., description="The status of the company")
    last_updated: Optional[datetime] = Field(
        default=None, description="The last updated date of the company status"
    )


class CompanyEmployeeCount(BaseModel):
    total_employees: int = Field(..., description="The total number of employees")
    month: Optional[int] = Field(
        default=None, description="The month of the employee count"
    )
    year: Optional[int] = Field(
        default=None, description="The year of the employee count"
    )


class OtherSocialMedia(Enum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    CRUNCHBASE = "crunchbase"


class KeyExecutive(BaseModel):
    name: str = Field(..., description="The name of the key executive")
    title: str = Field(..., description="The title of the key executive")
    linkedin_url: Optional[str] = Field(
        default=None, description="The LinkedIn URL of the key executive"
    )
    twitter_url: Optional[str] = Field(
        default=None, description="The twitter URL of the key executive"
    )
    other_social_media_urls: Optional[Dict[OtherSocialMedia, str]] = Field(
        default=None, description="Other social media URLs of the key executive"
    )


class CompanyLocation(BaseModel):
    city: str = Field(..., description="The city of the company location")
    state: Optional[str] = Field(..., description="The state of the company location")
    country: Optional[str] = Field(
        ..., description="The country of the company location"
    )
    country_code: Optional[str] = Field(
        ..., description="The country code of the company location"
    )
    postal_code: Optional[str] = Field(
        ..., description="The postal code of the company location"
    )
    address: Optional[str] = Field(..., description="Office location")
    longitude: Optional[float] = Field(
        default=None, description="The longitude of the company location"
    )
    latitude: Optional[float] = Field(
        default=None, description="The latitude of the company location"
    )
    is_headquarter: Optional[bool] = Field(
        default=False, description="Whether the location is a headquarter"
    )


class SimilarCompany(BaseModel):
    company_name: str = Field(..., description="The name of the similar company")
    company_industries: List[str] = Field(
        default_factory=list, description="The industries of the similar company"
    )


class IncomeStatement(BaseModel):
    revenue: Optional[float]
    currency: Optional[str]
    net_income: Optional[float]
    gross_profit_margin: Optional[float]
    end_date: Optional[str]
    period_type: Optional[str]
    ebitda: Optional[float]
    gross_profit: Optional[float]


class CompanyData(BaseModel):
    company_name: str = Field(..., description="The name of the company")
    company_domain: str = Field(..., description="The domain of the company")
    company_industries: List[str] = Field(
        default_factory=list, description="The industries of the company"
    )
    company_founded_year: Optional[int] = Field(
        ..., description="The year the company was founded"
    )
    company_website_url: Optional[str] = Field(
        default=None, description="The website URL of the company"
    )
    company_funding_info: Optional[List[CompanyFundingInfo]] = Field(
        default_factory=list, description="The funding information of the company"
    )
    company_logo_url: Optional[str] = Field(
        default=None, description="The logo URL of the company"
    )
    company_status: CurrentCompanyStatus = Field(
        default_factory=lambda: CurrentCompanyStatus(
            status=CompanyStatus.ACTIVE, last_updated=None
        ),
        description="The status of the company",
    )
    company_description: Optional[str] = Field(
        default="", description="The description of the company"
    )
    key_executives: Optional[List[KeyExecutive]] = Field(
        default_factory=list, description="The key executives of the company"
    )
    company_type: Optional[str] = Field(
        default=None, description="The type of the company (e.g., private, public)"
    )
    company_linkedin_url: Optional[str] = Field(
        default=None, description="The LinkedIn URL of the company"
    )
    company_twitter_url: Optional[str] = Field(
        default=None, description="The Twitter URL of the company"
    )
    company_symbol: Optional[str] = Field(
        default=None, description="The stock symbol of the company"
    )
    company_operating_metrics: Optional[List[CompanyOperatingMetric]] = Field(
        default=None, description="The operating metrics of the company"
    )
    company_employee_counts: Optional[List[CompanyEmployeeCount]] = Field(
        default_factory=list, description="The employee counts of the company"
    )
    company_locations: Optional[List[CompanyLocation]] = Field(
        default_factory=list, description="The location information of the company"
    )
    similar_companies: Optional[List[SimilarCompany]] = Field(
        default_factory=list, description="The similar companies"
    )
    other_social_media_urls: Optional[Dict[OtherSocialMedia, str]] = Field(
        default=None, description="Other social media URLs of the company"
    )
    company_income_statements: Optional[List[IncomeStatement]] = Field(
        default=[], description="Income statements"
    )
