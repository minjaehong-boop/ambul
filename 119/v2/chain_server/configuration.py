"""Application configuration dataclasses."""

from chain_server.configuration_wizard import ConfigWizard, configclass, configfield


@configclass
class LLMConfig(ConfigWizard):
    """LLM server connection configuration."""

    server_url: str = configfield(
        "server_url", default="http://localhost:8000/v1",
        help_txt="OpenAI-compatible LLM server URL (e.g. vLLM endpoint).",
    )
    model_name: str = configfield(
        "model_name", default="Qwen/Qwen3-8B",
        help_txt="Model name served by the LLM server.",
    )


@configclass
class AppConfig(ConfigWizard):
    """Top-level application configuration."""

    llm: LLMConfig = configfield(
        "llm", env=False,
        help_txt="LLM server configuration.",
        default=LLMConfig(),
    )
