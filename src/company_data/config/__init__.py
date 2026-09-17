"""Configuration package.

Loads a local ``.env`` once at import time so settings work for every entry
point (CLI, scripts, tests) without each one calling ``load_dotenv`` itself.
This is what makes values such as ``GEMINI_API_KEY`` (or ``PG_CONNECTION_STRING``
/ ``LLM_MERGE_MODEL``) available to the modules below.

Real environment variables always win over ``.env`` entries.
"""

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True), override=False)