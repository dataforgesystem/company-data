import json


class ScrapingUtils:

    @staticmethod
    def get_search_query_url():
        return f"https://craft.co/graphql"

    @staticmethod
    def prepare_search_query_headers():
        headers = {
            "accept": "*/*",
            "accept-language": "en-GB,en;q=0.8",
            "content-type": "application/json",
            "origin": "https://craft.co",
            "priority": "u=1, i",
            "referer": "https://craft.co/amazon",
            "sec-ch-ua": '"Not=A?Brand";v="99", "Brave";v="151", "Chromium";v="151"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            # "Cookie": "cf_clearance=btFIipXqQrzBAEKRecea1pPwaLJjI32wH9ytMlK7aRM-1786601528-1.2.1.1-xjs7QuBDhvkcmmlJKIvuQmGcAlyilNOq31CffyqXGcbC3mwhZellny3C_u4Pud1TQU79SauAWBXOgQi7VxiPm7b0nDHNU5v71D8bUK5C9OyEERHUQZIKHwSc3eH73Y9TeNzbzOh388mvaMxH27vfZydQSbhgKXqwlGC6k3S7OQKdUH9Pg2eKcgqTHjBReGeYzsR3ETFIh2oh.D03gIrR7G3D__w_XbrlQ_Rf7YHgVSZtHpSPysYBiYf8fpANsSOQZVE2tg0N0n4uvSxYlck6dQMHxvh.2D3gMtkK_Ry8uu7G_s6tpk9Qx7PXIqkV4hQEgQXrx083fpwc.KuI_YrT821FfKwg7mWweWGJ.q2Diuo",
        }
        return headers

    @staticmethod
    def prepare_search_query_payload(query: str):
        return json.dumps(
            {
                "operationName": "UniversalSearch",
                "variables": {"query": query},
                "query": "query UniversalSearch($query: String\u0021) { universalSearch(query: $query) { ...UniversalSearchResult __typename }}fragment UniversalSearchResult on SearchSuggestion { company { ...CompanyWithLogo __typename } name type url __typename}fragment CompanyWithLogo on Company { id slug displayName logo { id url __typename } __typename}",
            }
        )
