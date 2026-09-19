import os


def _flag(name: str, default: bool) -> bool:
    """Reads a boolean environment flag ("1"/"true"/"yes"/"on")."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class MergeConfig:
    """How per-source crawler records are reconciled into one view.

    Merging is optional and off-heavy by design: stores keep one record per
    source, and answering from a single preferred source is the default.

    Strategies (``MERGE_STRATEGY``, default ``preferred``):

    - ``off``: never merge; every company resolves to its preferred-source
      record only. Deterministic, no LLM cost.
    - ``preferred`` (default): use the preferred source when it has a record;
      fall back to deterministic union *only* when the preferred source is
      missing. Still no LLM call.
    - ``union`` (algorithmic): deterministic union across all sources via
      :class:`DeterministicUnionMerger` - newest non-empty scalar wins,
      collections are de-duplicated unions. No LLM call.
    - ``llm``: reconcile with an LLM via :class:`LLMProfileMerger`.
      Optional, explicitly chosen - LLM-based merging is never the default.

    ``MERGE_PREFERRED_SOURCE`` (default ``craft``) selects the primary source
    for ``off``/``preferred``. ``MERGE_ENABLED=false`` is a legacy kill-switch
    that forces ``off``.
    """

    STRATEGY = os.getenv("MERGE_STRATEGY", "preferred").strip().lower()
    PREFERRED_SOURCE = os.getenv("MERGE_PREFERRED_SOURCE", "craft").strip().lower()

    if not _flag("MERGE_ENABLED", True):
        STRATEGY = "off"

    VALID_STRATEGIES: tuple[str, ...] = ("off", "preferred", "union", "llm")

    #: Strategies that reconcile across sources, and therefore need every
    #: source scraped. ``off``/``preferred`` answer from one record.
    MULTI_SOURCE_STRATEGIES: tuple[str, ...] = ("union", "llm")

    @classmethod
    def validated_strategy(cls) -> str:
        """The configured strategy, falling back to ``preferred`` when unknown."""
        if cls.STRATEGY not in cls.VALID_STRATEGIES:
            return "preferred"
        return cls.STRATEGY

    @classmethod
    def needs_all_sources(cls) -> bool:
        """Whether the active strategy consumes records from every source.

        Only ``union`` and ``llm`` reconcile across sources; ``off`` and
        ``preferred`` resolve from a single record, so scraping anything
        beyond the preferred source is wasted crawl/embed/store work.
        """
        return cls.validated_strategy() in cls.MULTI_SOURCE_STRATEGIES

    @classmethod
    def read_sources(cls) -> tuple[str, ...] | None:
        """Sources whose records every read (retrieval, fetch) may see.

        ``None`` means "no restriction" (multi-source strategies). Single-
        source strategies return ``(PREFERRED_SOURCE,)`` so a stale point or
        row from another source can never leak into a lookup, even when it
        still sits in the index.
        """
        if cls.needs_all_sources():
            return None
        return (cls.PREFERRED_SOURCE,)


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
