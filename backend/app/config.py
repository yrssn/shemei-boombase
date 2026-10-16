from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = "dev-secret-change-me-please-use-32-plus-bytes"
    access_token_expire_minutes: int = 720
    app_users: str = "admin:admin123"
    cors_origins: str = "http://localhost:5173"

    wecom_corp_id: str = ""
    wecom_corp_secret: str = ""
    wecom_docid: str = ""
    wecom_sheet_id: str = ""
    wecom_field_link: str = "帖子链接"
    wecom_field_caption: str = "原始文案"
    wecom_field_author: str = "作者"
    wecom_field_sentiment: str = "情绪"
    wecom_field_operator: str = "提交人"

    http_proxy_url: str = ""
    ig_sessionid: str = ""
    database_url: str = "sqlite:///./data.db"

    @property
    def users(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for item in self.app_users.split(","):
            item = item.strip()
            if not item or ":" not in item:
                continue
            username, password = item.split(":", 1)
            result[username.strip()] = password.strip()
        return result

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def wecom_configured(self) -> bool:
        return all([self.wecom_corp_id, self.wecom_corp_secret, self.wecom_docid, self.wecom_sheet_id])


@lru_cache
def get_settings() -> Settings:
    return Settings()
