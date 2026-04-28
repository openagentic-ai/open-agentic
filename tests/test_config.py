"""Test application config settings."""


from openagentic.config import SETTINGS, Settings


class TestSettings:
    def test_defaults(self):
        """验证 Settings 默认值存在且类型正确。"""
        assert Settings().APP_NAME == "OpenAgentic"
        assert Settings().APP_ENV == "development"
        assert Settings().APP_PORT == 8000
        assert Settings().APP_LOG_LEVEL == "INFO"

    def test_database_url_default(self):
        """默认 DATABASE_URL 指向本地开发 pg。"""
        url = Settings().DATABASE_URL
        assert "postgresql+asyncpg" in url or "postgresql" in url

    def test_jwt_defaults(self):
        """JWT 配置默认值。"""
        s = Settings()
        assert s.JWT_ALGORITHM == "HS256"
        assert s.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert s.JWT_REFRESH_TOKEN_EXPIRE_DAYS == 7

    def test_llm_defaults(self):
        """LLM 默认模型字段非空（.env 可能覆盖为其他 provider）。"""
        s = Settings()
        assert s.LITELLM_DEFAULT_MODEL, "LITELLM_DEFAULT_MODEL should not be empty"
        assert isinstance(s.OLLAMA_API_BASE, str)

    def test_cli_defaults(self):
        """CLI 相关配置默认值。"""
        s = Settings()
        assert s.CLI_REACT_MAX_ITERATIONS == 1000
        assert s.OPENAGENTIC_SKIP_PROVIDER_CHECK is False

    def test_model_config_allows_extra_ignore(self):
        """Settings 配置：extra='ignore' 忽略未知环境变量。"""
        s = Settings()
        assert s.model_config.get("extra") == "ignore"

    def test_global_singleton(self):
        """SETTINGS 全局实例应与 Settings() 类型相同。"""
        assert isinstance(SETTINGS, Settings)
