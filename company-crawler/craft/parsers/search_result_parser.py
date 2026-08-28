from base.search_parser import SearchResponseParser
from interfaces.search_response import ISearchResponse
from typing import List
from logger import get_logger
from craft.utils.uri_utils import UriUtils
import json

logger = get_logger(__name__)


class CraftSearchParser(SearchResponseParser):
    def parse(self, data) -> List[ISearchResponse]:
        try:
            dict_data = json.loads(data)
            company_data = dict_data.get("data", {}).get("universalSearch", [])
            search_responses: List[ISearchResponse] = []
            for search_data in company_data:
                company_search_data = search_data.get("company", {})
                company_name = company_search_data.get("displayName")
                slug = company_search_data.get("slug")
                source_url = UriUtils.build_craft_source_page_url(slug)
                logo_url = company_search_data.get("logo", {}).get("url")
                search_response_data = ISearchResponse(
                    company_name=company_name,
                    source_url=source_url,
                    logo_url=logo_url,
                    slug=slug,
                )
                search_responses.append(search_response_data)
            return search_responses

        except Exception as ex:
            logger.exception(f"Error while parsing search response: {ex}")
