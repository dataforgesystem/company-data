"""Persistent LLM response cache (exact match)."""

import hashlib
import warnings
from collections.abc import Sequence

import diskcache
from langchain_core.caches import RETURN_VAL_TYPE, BaseCache
from langchain_core.globals import set_llm_cache
from langchain_core.load import dumps, loads

from company_data.config.cache_configs import CacheConfig
from company_data.utils.logger import CustomLogger

logger = CustomLogger().get_logger()

# ``loads`` is LangChain's own deserializer for cacheable generations and is
# the documented companion to ``dumps``. It emits a beta notice on first use,
# which adds noise to logs for a deliberate dependency.
warnings.filterwarnings(
    "ignore", message=r".*The function `loads` is in beta.*", category=Warning
)


class DiscoResponseCache(BaseCache):
    """``BaseCache`` implementation backed by ``diskcache``.

    Registered with :func:`langchain_core.globals.set_llm_cache`, it short
    circuits any model call whose prompt and model configuration were already
    answered. This also covers ``with_structured_output`` calls, because the
    structured runnable still invokes the chat model underneath, which is what
    stops a repeated agent run from re-spending hosted-model quota.

    Because the key includes the prompt *and* the model configuration, any
    change to either one is a miss - a cache hit can never return a response
    produced by a different model or a different prompt.
    """

    def __init__(self, directory: str, expiry_seconds: int | None = None) -> None:
        self.directory = directory
        self.expiry_seconds = expiry_seconds
        self._cache = diskcache.Cache(directory)

    @staticmethod
    def _key(prompt: str, llm_string: str) -> str:
        """Stable cache key for a (prompt, model configuration) pair."""
        digest = hashlib.sha256(f"{llm_string}\x00{prompt}".encode()).hexdigest()
        return f"llm:{digest}"

    def lookup(self, prompt: str, llm_string: str) -> RETURN_VAL_TYPE | None:
        """Returns cached generations, or ``None`` on a miss."""
        payload = self._cache.get(self._key(prompt, llm_string))
        if payload is None:
            return None
        # "core" is LangChain's own set of generation/message classes; the
        # entries are written by this process, never by untrusted input.
        return loads(payload, allowed_objects="core")

    def update(
        self, prompt: str, llm_string: str, return_val: RETURN_VAL_TYPE
    ) -> None:
        """Stores generations for a (prompt, model configuration) pair."""
        self._cache.set(
            self._key(prompt, llm_string),
            dumps(return_val),
            expire=self.expiry_seconds,
        )

    def clear(self, **kwargs: object) -> None:
        """Drops every cached response."""
        self._cache.clear()

    def close(self) -> None:
        """Releases the underlying disk cache."""
        self._cache.close()


def configure_llm_cache(
    enabled: bool = CacheConfig.LLM_CACHE_ENABLED,
    directory: str = CacheConfig.LLM_CACHE_DIR,
    expiry_seconds: int = CacheConfig.LLM_CACHE_EXPIRY_SECONDS,
) -> DiscoResponseCache | None:
    """Installs the shared response cache as LangChain's global LLM cache.

    Idempotent and safe to call from the composition root; returns ``None``
    when caching is disabled via ``LLM_CACHE_ENABLED=false``.
    """
    if not enabled:
        logger.info("LLM response cache disabled (LLM_CACHE_ENABLED=false).")
        return None

    cache = DiscoResponseCache(directory, expiry_seconds)
    set_llm_cache(cache)
    logger.info(
        f"LLM response cache enabled at {directory!r} "
        f"(ttl={expiry_seconds}s, exact prompt+model match)."
    )
    return cache