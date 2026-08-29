from os import stat
from typing import Any, Dict, List

import sys
from pathlib import Path


from base.parser import Parser
from models.company_data import (
    CompanyData,
    CurrentCompanyStatus,
    OtherSocialMedia,
    CompanyFundingInfo,
    KeyExecutive,
    CompanyEmployeeCount,
    CompanyLocation,
    SimilarCompany,
    IncomeStatement,
)
import json
from utils.general_utils import GeneralUtils
from global_utils.uri_utils import UriUtils
from global_utils.currency_parser import CurrencyParser


class CraftParser(Parser):

    def _extract_company_basic_info(self, raw_company_data: Dict) -> CompanyData:
        company_name = raw_company_data.get("displayName", "")
        company_description = raw_company_data.get("longDescription", "")
        homepage = raw_company_data.get("homepage", "")
        linkedin = raw_company_data.get("linkedin", "")
        twitter = raw_company_data.get("twitter", "")
        instagram = raw_company_data.get("instagram", "")
        facebook = raw_company_data.get("facebook", "")
        crunchbase = raw_company_data.get("crunchbase", "")
        company_status = raw_company_data.get("status", "")
        company_domain = UriUtils.extract_domain_from_url(homepage)
        company_founded_year = raw_company_data.get("foundedYear", "")
        status = GeneralUtils.handle_current_status(company_status)
        current_date = GeneralUtils.get_current_date()
        company_type = raw_company_data.get("companyType")
        stock_ticker = raw_company_data.get("stockTicker", "")
        other_social_links = {
            OtherSocialMedia.INSTAGRAM: instagram,
            OtherSocialMedia.FACEBOOK: facebook,
            OtherSocialMedia.CRUNCHBASE: crunchbase,
        }
        logo_url = raw_company_data.get("logo", {}).get("id", "")
        company_data: CompanyData = CompanyData(
            company_name=company_name,
            company_domain=company_domain,
            company_founded_year=company_founded_year,
            company_linkedin_url=linkedin,
            company_twitter_url=twitter,
            company_status=CurrentCompanyStatus(
                status=status, last_updated=current_date
            ),
            other_social_media_urls=other_social_links,
            company_description=company_description,
            company_website_url=homepage,
            company_logo_url=logo_url,
            company_type=company_type,
            company_symbol=stock_ticker,
        )
        return company_data

    def _parse_total_funding(
        self, company_key_data: Dict, raw_company_data: Dict
    ) -> List[CompanyFundingInfo]:
        company_funding_info: List[CompanyFundingInfo] = []
        total_funding_id = company_key_data.get("totalFunding", {}).get("id", "")

        if total_funding_id:
            raw_funding_info = raw_company_data.get(total_funding_id, {})
            currency_symbol = raw_funding_info.get("currencySymbol", "")
            value = raw_funding_info.get("value", 0)
            normalised_symbol: Any = CurrencyParser.get_codes_by_symbol(currency_symbol)
            if normalised_symbol:
                normalised_symbol = normalised_symbol[0]
            funding_info = CompanyFundingInfo(
                funding_round="unknown",
                funding_amount=value,
                funding_currency=normalised_symbol,
            )
            company_funding_info.append(funding_info)

        return company_funding_info

    def _parse_employee_count(
        self, company_key_data: Dict, raw_company_data: Dict
    ) -> List[CompanyEmployeeCount]:
        parsed_employee_counts: List[CompanyEmployeeCount] = []

        raw_employees_numbers = company_key_data.get("employees", [])
        for raw_employee_number in raw_employees_numbers:
            raw_id = raw_employee_number.get("id")
            typename = raw_employee_number.get("typename")

            if raw_id and typename and typename == "EmployeeNumber":
                raw_employee_data = raw_company_data.get(raw_id)
                raw_employee_count: int = raw_employee_data.get("employeeNumber", None)
                raw_date_str = raw_employee_data.get("date", None)
                date = GeneralUtils.parse_date(raw_date_str)
                parsed_employee_count = CompanyEmployeeCount(
                    total_employees=raw_employee_count, month=date.month, year=date.year
                )
                parsed_employee_counts.append(parsed_employee_count)
        return parsed_employee_counts

    def _parse_key_executives(
        self, company_key_data: Dict, raw_company_data: Dict[str, Any]
    ) -> List[KeyExecutive]:
        parsed_key_executives: List[KeyExecutive] = []
        raw_key_executives: List[Any] = company_key_data.get("keyExecutives", [])
        for executive in raw_key_executives:
            executive_id = executive.get("id")
            typename = executive.get("typename")

            if typename == "KeyExecutive":
                raw_executive_data: Any = raw_company_data.get(executive_id)
                executive_name: Any = raw_executive_data.get("name")
                executive_title: Any = raw_executive_data.get("title")
                executive_linkedin: Any = raw_executive_data.get("linkedin")
                executive_twitter: Any = raw_executive_data.get("twitter")
                executive_facebook: Any = raw_executive_data.get("facebook")
                other_social_media = other_social_links = {
                    OtherSocialMedia.FACEBOOK: executive_facebook
                }

                parsed_executive_data = KeyExecutive(
                    name=executive_name,
                    title=executive_title,
                    linkedin_url=executive_linkedin,
                    twitter_url=executive_twitter,
                    other_social_media_urls=other_social_media,
                )
                parsed_key_executives.append(parsed_executive_data)
        return parsed_key_executives

    def _parse_locations(
        self, company_key_data: Dict, raw_company_data: Dict
    ) -> List[CompanyLocation]:
        parsed_locations = []

        raw_locations_metadata = company_key_data.get("locations", [])

        for location_metadata in raw_locations_metadata:
            raw_location_id = location_metadata.get("id")
            raw_location = raw_company_data.get(raw_location_id)
            typename = raw_location.get("__typename")

            if typename == "Location":
                raw_address = raw_location.get("address", "")
                raw_city = raw_location.get("city", "")
                raw_state = raw_location.get("state", "")
                raw_country = raw_location.get("countryName")
                raw_country_code = raw_location.get("countryCode")
                raw_latitude = raw_location.get("latitude")
                raw_long = raw_location.get("longitude")
                is_headq = raw_location.get("hq", False)
                parsed_location_data = CompanyLocation(
                    city=raw_city,
                    state=raw_state,
                    country=raw_country,
                    country_code=raw_country_code,
                    latitude=raw_latitude,
                    longitude=raw_long,
                    address=raw_address,
                    postal_code=None,
                    is_headquarter=is_headq,
                )
                parsed_locations.append(parsed_location_data)

        return parsed_locations

    def _parse_tags(self, raw_tags: List[Dict], raw_company_data: Dict) -> List[str]:
        tags = set()
        for raw_tag in raw_tags:
            tag_id = raw_tag.get("id")
            typename = raw_tag.get("typename")
            if typename == "Tag":
                raw_tag_data = raw_company_data.get(tag_id)
                raw_tag_name: str = raw_tag_data.get("name", "")
                tags.add(raw_tag_name.lower())
        return list(tags)

    def _parse_similar_companies(
        self, company_key_data: Dict, raw_company_data: Dict
    ) -> List[SimilarCompany]:
        parsed_similar_companies = []
        raw_similar_metadata = company_key_data.get("competitors", [])

        for similar_metadata in raw_similar_metadata:
            raw_location_id = similar_metadata.get("id")
            raw_similar_company = raw_company_data.get(raw_location_id)
            typename = raw_similar_company.get("__typename")

            if typename == "Company":
                raw_company_name = raw_similar_company.get("displayName")
                company_industries = self._parse_tags(
                    raw_similar_company.get("tags"), raw_company_data
                )
                similar_company = SimilarCompany(
                    company_name=raw_company_name, company_industries=company_industries
                )
                parsed_similar_companies.append(similar_company)

        return parsed_similar_companies

    def _parse_income_statements(
        self, company_key_data: Dict, raw_company_data: Dict
    ) -> List[IncomeStatement]:
        parsed_income_statements = []
        raw_income_statements = company_key_data.get("incomeStatements", [])
        for raw_income_statement in raw_income_statements:
            raw_income_statement_id = raw_income_statement.get("id")

            raw_income_statement_data = raw_company_data.get(raw_income_statement_id)
            raw_revenue = raw_income_statement_data.get("revenue", None)
            raw_currency = raw_income_statement_data.get("currencyIsoCode", None)
            raw_net_income = raw_income_statement_data.get("netIncome", None)
            raw_gross_profit_margin = raw_income_statement_data.get(
                "grossProfitMargin", None
            )
            raw_ebitda = raw_income_statement_data.get("ebit", None)
            raw_gross_profit = raw_income_statement_data.get("grossProfit", None)

            raw_period_id = raw_income_statement_data.get("period", {}).get("id")
            raw_period_data = {}
            if raw_period_id:
                raw_period_data = raw_company_data.get(raw_period_id)
            raw_end_date = raw_period_data.get("displayEndDate", None)
            raw_period_type = raw_period_data.get("periodType", None)

            parsed_income_statement = IncomeStatement(
                revenue=raw_revenue,
                currency=raw_currency,
                net_income=raw_net_income,
                gross_profit_margin=raw_gross_profit_margin,
                end_date=raw_end_date,
                period_type=raw_period_type,
                ebitda=raw_ebitda,
                gross_profit=raw_gross_profit,
            )

            parsed_income_statements.append(parsed_income_statement)

        return parsed_income_statements

    def parse(self, data: str) -> CompanyData:
        json_data = json.loads(data)
        company_key_data: Any = GeneralUtils.search_data_by_key(
            json_data, r"^Company:\d+$"
        )
        company_data = self._extract_company_basic_info(company_key_data)
        company_data.company_funding_info = self._parse_total_funding(
            company_key_data, json_data
        )
        company_data.key_executives = self._parse_key_executives(
            company_key_data, json_data
        )
        company_data.company_employee_counts = self._parse_employee_count(
            company_key_data, json_data
        )
        company_data.company_locations = self._parse_locations(
            company_key_data, json_data
        )
        company_data.company_industries = self._parse_tags(
            company_key_data.get("tags"), json_data
        )
        company_data.similar_companies = self._parse_similar_companies(
            company_key_data, json_data
        )
        company_data.company_income_statements = self._parse_income_statements(
            company_key_data, json_data
        )

        return company_data  #! TESTING


if __name__ == "__main__":
    # Example usage
    craft_parser = CraftParser()
    sample_data = "<html>Sample Craft data</html>"  # Replace with actual Craft data
    with open(
        "/mnt/storage/My Programming project/company-data/company-crawler/craft_data.json",
        "r",
    ) as f:
        sample_data = f.read()
    company_data = craft_parser.parse(sample_data)
    with open(
        "/mnt/storage/My Programming project/company-data/company-crawler/parsed_craft_data.json",
        "w",
    ) as f:
        json.dump(company_data, f, indent=2)
