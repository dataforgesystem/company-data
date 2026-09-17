import os


class CrawlerConfig:
    """``company_data_crawler`` settings, overridable via environment vars."""

    # The crawler persists one disk cache per model it stores (``CompanyData/``,
    # ``ISearchResponse/``, ``TickerResolution/``) under whatever base directory
    # it is given, falling back to the process working directory. Point it at a
    # dedicated directory so runtime caches never litter the repository root.
    CACHE_DIR = os.getenv(
        "CRAWLER_CACHE_DIR",
        os.path.join(os.getcwd(), ".cache", "crawler"),
    )
