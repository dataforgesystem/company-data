import re
import tldextract


class UriUtils:
    @staticmethod
    def build_craft_source_page_url(slug: str):
        return f"https://craft.co/{slug}"

    @staticmethod
    def extract_domain_from_url(url: str) -> str:
        """
        Extracts the domain from a given URL.
        """
        if not url:
            return ""
        ext = tldextract.extract(url)
        return ext.top_domain_under_public_suffix
