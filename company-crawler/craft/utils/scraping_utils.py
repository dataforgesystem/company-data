class ScrapingUtils:

    @staticmethod
    def get_search_query_url():
        return f"https://craft.co/graphql"

    @staticmethod
    def prepare_search_query_headers():
        headers_list = {
            "accept": "*/*",
            "accept-language": "en-GB,en;q=0.8",
            "content-type": "application/json",
            "origin": "https://craft.co",
            "priority": "u=1, i",
            "referer": "https://craft.co/google",
            "sec-ch-ua": '"Not=A?Brand";v="99", "Brave";v="151", "Chromium";v="151"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Linux",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        }
        return headers_list

    @staticmethod
    def prepare_search_query_payload(query: str):
        return {
            "operationName": "UniversalSearch",
            "variables": {"query": query},
            "query": "query UniversalSearch($query: String\u0021) { universalSearch(query: $query) { ...UniversalSearchResult __typename }}fragment UniversalSearchResult on SearchSuggestion { company { ...CompanyWithLogo __typename } name type url __typename}fragment CompanyWithLogo on Company { id slug displayName logo { id url __typename } __typename}",
        }
