import os


def _flag(name: str, default: bool) -> bool:
    """Reads a boolean environment flag ("1"/"true"/"yes"/"on")."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class CacheConfig:
    """Caching settings, overridable via environment variables.

    Two independent layers protect rate-limited or paid model calls:

    - ``llm``: an exact-match cache of model responses, keyed by the full
      prompt plus the model configuration. Re-running the same step then costs
      no API call at all. Always correct: identical input, identical output.
    - ``query``: a semantic cache of whole agent answers, keyed by the query
      embedding. Re-asking the same (or a very similarly worded) question
      skips the graph entirely, including crawling and merging.

    Both are on by default and can be switched off with
    ``LLM_CACHE_ENABLED=false`` / ``QUERY_CACHE_ENABLED=false``.
    """

    # ------------------------------------------------- exact-match LLM cache
    LLM_CACHE_ENABLED = _flag("LLM_CACHE_ENABLED", True)
    LLM_CACHE_DIR = os.getenv(
        "LLM_CACHE_DIR", os.path.join(os.getcwd(), ".cache", "llm")
    )
    # Responses are model output, so they are cached for a limited window
    # rather than forever (default: one week).
    LLM_CACHE_EXPIRY_SECONDS = int(
        os.getenv("LLM_CACHE_EXPIRY_SECONDS", str(7 * 24 * 60 * 60))
    )

    # ---------------------------------------------------- semantic query cache
    QUERY_CACHE_ENABLED = _flag("QUERY_CACHE_ENABLED", True)
    QUERY_CACHE_COLLECTION = os.getenv("QUERY_CACHE_COLLECTION", "query_cache")
    # Cosine similarity required for a semantic hit.
    #
    # This is a correctness/latency trade-off, not just a tuning knob. Two
    # questions can be nearly identical as sentences yet ask for different
    # things ("competitors of Tesla" vs "customers of Tesla"), and a semantic
    # hit skips the LLM entirely, so a false hit returns the wrong answer with
    # no way to notice. The default is deliberately conservative: it catches
    # repeats and trivial rewordings. Set to 1.0 for an exact-text cache, or
    # lower it only when answer variety matters less than avoiding API cost.
    QUERY_CACHE_THRESHOLD = float(os.getenv("QUERY_CACHE_THRESHOLD", "0.97"))
    # Cached answers go stale as companies change; default 24 hours.
    QUERY_CACHE_TTL_SECONDS = int(
        os.getenv("QUERY_CACHE_TTL_SECONDS", str(24 * 60 * 60))
    )