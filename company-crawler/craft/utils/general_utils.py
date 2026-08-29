import re
from typing import Optional
from typing import Dict, Any
from models.company_data import CompanyStatus
from datetime import datetime, timezone
from dateutil.parser import parse


class GeneralUtils:
    @staticmethod
    def search_data_by_key(data, key_pattern) -> Optional[Dict[str, Any]]:
        """
        Returns first matching key-value pair in the data dictionary based on the provided regex pattern.
        """
        for key, value in data.items():
            if re.match(key_pattern, key):
                return value
        return None

    @staticmethod
    def handle_current_status(current_str: str) -> CompanyStatus:
        # match with regex to find the status in the string
        # find the closest active match to the status in the string
        status_match = re.search(
            r"(active|inactive|acquired|bankrupt|closed|unknown)",
            current_str,
            re.IGNORECASE,
        )
        if status_match:
            status_str = status_match.group(1).lower()
            if status_str == "active":
                return CompanyStatus.ACTIVE
            elif status_str == "inactive":
                return CompanyStatus.INACTIVE
            elif status_str == "acquired":
                return CompanyStatus.ACQUIRED
            elif status_str == "bankrupt":
                return CompanyStatus.BANKRUPT
            elif status_str == "closed":
                return CompanyStatus.CLOSED
        return CompanyStatus.UNKNOWN

    @staticmethod
    def get_current_date():
        return datetime.now(tz=timezone.utc)

    @staticmethod
    def parse_date(date_str: str):
        if not date_str:
            return None
        return parse(date_str)
