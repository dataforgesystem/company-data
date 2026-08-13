import pytest
from datetime import datetime
from pydantic import ValidationError
from models.company_data import (
    CompanyFundingInfo,
    CompanyFinancials,
    CompanyOperatingMetrics,
    CompanyStatus,
    CurrentCompanyStatus,
    CompanyEmployeeCount,
    CompanyLocation,
    CompanyData,
)


class TestCompanyFundingInfo:
    """Test CompanyFundingInfo model"""

    def test_required_fields(self):
        """Test that required fields are enforced"""
        with pytest.raises(ValidationError):
            CompanyFundingInfo()

    def test_valid_funding_info(self):
        """Test creating valid CompanyFundingInfo"""
        funding = CompanyFundingInfo(
            funding_round="Series A",
            funding_amount=5000000.0,
            funding_currency="USD",
            funding_date="2023-01-15",
            investors=["Investor A", "Investor B"],
        )
        assert funding.funding_round == "Series A"
        assert funding.funding_amount == 5000000.0
        assert funding.funding_currency == "USD"
        assert len(funding.investors) == 2

    def test_empty_investors_list(self):
        """Test with empty investors list (default)"""
        funding = CompanyFundingInfo(
            funding_round="Seed",
            funding_amount=500000.0,
            funding_currency="USD",
            funding_date="2022-06-01",
        )
        assert funding.investors == []

    def test_optional_funding_date(self):
        """Test that funding_date is optional"""
        funding = CompanyFundingInfo(
            funding_round="Series A",
            funding_amount=5000000.0,
            funding_currency="USD",
            investors=["Investor A"],
        )
        assert funding.funding_date is None


class TestCompanyFinancials:
    """Test CompanyFinancials model"""

    def test_valid_financials(self):
        """Test creating valid CompanyFinancials"""
        financials = CompanyFinancials(
            revenue=1000000.0,
            currency="USD",
            financial_year=2023,
            ebitda=250000.0,
        )
        assert financials.revenue == 1000000.0
        assert financials.financial_year == 2023

    def test_all_fields_required(self):
        """Test that all fields are required"""
        with pytest.raises(ValidationError):
            CompanyFinancials(revenue=1000000.0)


class TestCompanyOperatingMetrics:
    """Test CompanyOperatingMetrics model"""

    def test_valid_metrics(self):
        """Test creating valid CompanyOperatingMetrics"""
        metrics = CompanyOperatingMetrics(
            revenue=5000000.0,
            profit=1000000.0,
            expenses=4000000.0,
            growth_rate=0.25,
            market_share=0.15,
        )
        assert metrics.revenue == 5000000.0
        assert metrics.growth_rate == 0.25

    def test_invalid_type_conversion(self):
        """Test type validation"""
        with pytest.raises(ValidationError):
            CompanyOperatingMetrics(
                revenue="not a number",
                profit=1000000.0,
                expenses=4000000.0,
                growth_rate=0.25,
                market_share=0.15,
            )


class TestCompanyStatus:
    """Test CompanyStatus enum"""

    def test_all_status_values(self):
        """Test all CompanyStatus enum values"""
        assert CompanyStatus.ACTIVE.value == "active"
        assert CompanyStatus.INACTIVE.value == "inactive"
        assert CompanyStatus.ACQUIRED.value == "acquired"
        assert CompanyStatus.BANKRUPT.value == "bankrupt"
        assert CompanyStatus.CLOSED.value == "closed"


class TestCurrentCompanyStatus:
    """Test CurrentCompanyStatus model"""

    def test_valid_status(self):
        """Test creating valid CurrentCompanyStatus"""
        status = CurrentCompanyStatus(
            status=CompanyStatus.ACTIVE, last_updated=datetime.now()
        )
        assert status.status == CompanyStatus.ACTIVE
        assert status.last_updated is not None

    def test_optional_last_updated(self):
        """Test that last_updated is optional"""
        status = CurrentCompanyStatus(status=CompanyStatus.ACTIVE)
        assert status.last_updated is None

    def test_invalid_status_enum(self):
        """Test that invalid status value raises error"""
        with pytest.raises(ValidationError):
            CurrentCompanyStatus(status="invalid_status")


class TestCompanyEmployeeCount:
    """Test CompanyEmployeeCount model"""

    def test_valid_employee_count(self):
        """Test creating valid CompanyEmployeeCount"""
        emp_count = CompanyEmployeeCount(total_employees=100, month=8, year=2023)
        assert emp_count.total_employees == 100

    def test_optional_month_and_year(self):
        """Test that month and year are optional"""
        emp_count = CompanyEmployeeCount(total_employees=50)
        assert emp_count.month is None
        assert emp_count.year is None

    def test_total_employees_required(self):
        """Test that total_employees is required"""
        with pytest.raises(ValidationError):
            CompanyEmployeeCount()


class TestCompanyLocation:
    """Test CompanyLocation model"""

    def test_valid_location(self):
        """Test creating valid CompanyLocation"""
        location = CompanyLocation(
            city="San Francisco",
            state="CA",
            country="USA",
            postal_code="94105",
        )
        assert location.city == "San Francisco"
        assert location.country == "USA"

    def test_all_fields_required(self):
        """Test that all location fields are required"""
        with pytest.raises(ValidationError):
            CompanyLocation(city="San Francisco")


class TestCompanyData:
    """Test CompanyData model"""

    def test_minimal_valid_company(self):
        """Test creating CompanyData with only required fields"""
        company = CompanyData(
            company_name="Tech Corp",
            company_domain="techcorp.com",
            company_size="100-500",
            company_founded_year=2015,
        )
        assert company.company_name == "Tech Corp"
        assert company.company_domain == "techcorp.com"
        # Check defaults
        assert company.company_website is None
        assert company.company_industries == []
        assert company.company_funding_info == []

    def test_full_valid_company(self):
        """Test creating CompanyData with all fields"""
        location = CompanyLocation(
            city="San Francisco",
            state="CA",
            country="USA",
            postal_code="94105",
        )
        funding = CompanyFundingInfo(
            funding_round="Series A",
            funding_amount=5000000.0,
            funding_currency="USD",
            investors=["VC Fund A"],
        )
        metrics = CompanyOperatingMetrics(
            revenue=1000000.0,
            profit=200000.0,
            expenses=800000.0,
            growth_rate=0.30,
            market_share=0.05,
        )
        emp_count = CompanyEmployeeCount(total_employees=50, month=8, year=2023)

        company = CompanyData(
            company_name="Tech Corp",
            company_website="https://techcorp.com",
            company_domain="techcorp.com",
            company_industries=["Technology", "SaaS"],
            company_size="50-100",
            company_founded_year=2015,
            company_website_url="https://techcorp.com",
            company_funding_info=[funding],
            company_logo_url="https://techcorp.com/logo.png",
            company_status=CurrentCompanyStatus(status=CompanyStatus.ACTIVE),
            company_description="A tech company",
            company_headquarters="San Francisco, CA",
            company_ceo="John Doe",
            company_type="Private",
            company_linkedin_url="https://linkedin.com/company/techcorp",
            company_twitter_url="https://twitter.com/techcorp",
            company_symbol="TECH",
            company_operating_metrics=metrics,
            company_employee_counts=[emp_count],
            company_locations=[location],
        )

        assert company.company_name == "Tech Corp"
        assert len(company.company_industries) == 2
        assert len(company.company_locations) == 1
        assert company.company_status.status == CompanyStatus.ACTIVE

    def test_missing_required_company_name(self):
        """Test that company_name is required"""
        with pytest.raises(ValidationError):
            CompanyData(
                company_domain="test.com",
                company_size="100",
                company_founded_year=2020,
            )

    def test_optional_fields_with_defaults(self):
        """Test optional fields have proper defaults"""
        company = CompanyData(
            company_name="Test Corp",
            company_domain="test.com",
            company_size="50",
            company_founded_year=2020,
        )
        assert company.company_website is None
        assert company.company_ceo is None
        assert company.company_industries == []
        assert company.company_employee_counts == []
        assert company.company_locations == []

    def test_type_validation_on_founded_year(self):
        """Test that founded_year must be int"""
        # Pydantic v2 coerces numeric strings to int, so test with truly invalid type
        with pytest.raises(ValidationError):
            CompanyData(
                company_name="Test Corp",
                company_domain="test.com",
                company_size="50",
                company_founded_year=[2020],  # Should be int, not list
            )


class TestIntegration:
    """Integration tests for complex scenarios"""

    def test_company_with_multiple_funding_rounds(self):
        """Test company with multiple funding rounds"""
        funding_rounds = [
            CompanyFundingInfo(
                funding_round="Seed",
                funding_amount=500000.0,
                funding_currency="USD",
                investors=["Angel Investor"],
            ),
            CompanyFundingInfo(
                funding_round="Series A",
                funding_amount=5000000.0,
                funding_currency="USD",
                investors=["VC Fund A", "VC Fund B"],
            ),
        ]

        company = CompanyData(
            company_name="Growth Startup",
            company_domain="growthstartup.com",
            company_size="20-50",
            company_founded_year=2021,
            company_funding_info=funding_rounds,
        )

        assert len(company.company_funding_info) == 2
        assert company.company_funding_info[0].funding_round == "Seed"
        assert company.company_funding_info[1].funding_round == "Series A"

    def test_company_with_multiple_locations(self):
        """Test company with multiple office locations"""
        locations = [
            CompanyLocation(
                city="San Francisco",
                state="CA",
                country="USA",
                postal_code="94105",
            ),
            CompanyLocation(
                city="New York",
                state="NY",
                country="USA",
                postal_code="10001",
            ),
            CompanyLocation(
                city="London",
                state="England",
                country="UK",
                postal_code="EC1A 1BB",
            ),
        ]

        company = CompanyData(
            company_name="Global Tech",
            company_domain="globaltech.com",
            company_size="200-500",
            company_founded_year=2010,
            company_locations=locations,
        )

        assert len(company.company_locations) == 3
        assert company.company_locations[0].city == "San Francisco"
        assert company.company_locations[2].country == "UK"

    def test_serialization_to_dict(self):
        """Test that models can be serialized to dict"""
        company = CompanyData(
            company_name="Test Corp",
            company_domain="test.com",
            company_size="100",
            company_founded_year=2020,
        )
        company_dict = company.model_dump()
        assert isinstance(company_dict, dict)
        assert company_dict["company_name"] == "Test Corp"

    def test_serialization_to_json(self):
        """Test that models can be serialized to JSON"""
        company = CompanyData(
            company_name="Test Corp",
            company_domain="test.com",
            company_size="100",
            company_founded_year=2020,
        )
        company_json = company.model_dump_json()
        assert isinstance(company_json, str)
        assert "Test Corp" in company_json
