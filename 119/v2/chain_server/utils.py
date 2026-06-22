"""Utility functions — minimal version for triage_rag projects."""

import logging
import os
from functools import lru_cache
from typing import TYPE_CHECKING

from chain_server import configuration

if TYPE_CHECKING:
    from chain_server.configuration_wizard import ConfigWizard

logger = logging.getLogger(__name__)


@lru_cache
def get_config() -> "ConfigWizard":
    """Parse application configuration from file or environment variables.

    Config file path is read from APP_CONFIG_FILE env var (default: /dev/null).
    LLM settings can also be set via:
      APP_LLM_SERVER_URL  — e.g. http://localhost:8000/v1
      APP_LLM_MODEL_NAME  — e.g. Qwen/Qwen3-8B
    """
    config_file = os.environ.get("APP_CONFIG_FILE", "/dev/null")
    config = configuration.AppConfig.from_file(config_file)
    if config:
        return config
    raise RuntimeError("Unable to load configuration.")
