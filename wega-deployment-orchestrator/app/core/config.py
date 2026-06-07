from functools import lru_cache
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Wega Deployment Orchestrator"
    app_version: str = "1.0.0"
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8091)
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    cors_allowed_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")
    ci_agent_url: str = Field(default="http://localhost:8092")
    cd_agent_url: str = Field(default="")
    conversation_memory_limit: int = Field(default=20)
    repository_lookup_timeout_seconds: float = Field(default=15.0)
    repository_push_timeout_seconds: float = Field(default=60.0)
    google_cloud_project: str = Field(default="")
    gcp_secret_manager_project: str = Field(default="")
    repository_lookup_allow_local_debug_bypass: bool = Field(default=True)
    repository_lookup_identity_header: str = Field(default="X-WEGA-Principal")
    repository_lookup_roles_header: str = Field(default="X-WEGA-Roles")
    repository_lookup_authorized_users: str = Field(default="")
    repository_lookup_authorized_roles: str = Field(default="")
    repository_lookup_service_token: str = Field(default="")
    repository_lookup_service_token_secret_name: str = Field(default="")
    github_allowed_hosts: str = Field(default="github.com,api.github.com")
    gitlab_allowed_hosts: str = Field(default="gitlab.com")
    azure_devops_allowed_hosts: str = Field(default="dev.azure.com,*.visualstudio.com")
    harness_allowed_hosts: str = Field(default="app.harness.io,git.harness.io")

    github_repository_url: str = Field(default="")
    github_pat_token: str = Field(default="")

    gitlab_repository_url: str = Field(default="")
    gitlab_pat_token: str = Field(default="")

    azure_devops_repository_url: str = Field(default="")
    azure_devops_pat_token: str = Field(default="")
    azure_devops_secret_name: str = Field(default="")
    azure_devops_organization_url: str = Field(default="")
    azure_devops_default_project: str = Field(default="")
    azure_devops_default_pipeline_folder: str = Field(default="")

    harness_base_url: str = Field(default="https://app.harness.io")
    harness_account_identifier: str = Field(default="")
    harness_org_identifier: str = Field(default="default")
    harness_project_identifier: str = Field(default="")
    harness_secret_name: str = Field(default="")
    harness_pat_token: str = Field(default="")
    repository_push_author_name: str = Field(default="WEGA Build AI")
    repository_push_author_email: str = Field(default="wega-build-ai@local")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def repository_lookup_authorized_users_list(self) -> list[str]:
        return [value.strip().lower() for value in self.repository_lookup_authorized_users.split(",") if value.strip()]

    @property
    def repository_lookup_authorized_roles_list(self) -> list[str]:
        return [value.strip().lower() for value in self.repository_lookup_authorized_roles.split(",") if value.strip()]

    @property
    def github_allowed_hosts_list(self) -> list[str]:
        return [value.strip().lower() for value in self.github_allowed_hosts.split(",") if value.strip()]

    @property
    def gitlab_allowed_hosts_list(self) -> list[str]:
        return [value.strip().lower() for value in self.gitlab_allowed_hosts.split(",") if value.strip()]

    @property
    def azure_devops_allowed_hosts_list(self) -> list[str]:
        return [value.strip().lower() for value in self.azure_devops_allowed_hosts.split(",") if value.strip()]

    @property
    def harness_allowed_hosts_list(self) -> list[str]:
        return [value.strip().lower() for value in self.harness_allowed_hosts.split(",") if value.strip()]

    @property
    def harness_base_url_normalized(self) -> str:
        return self.harness_base_url.strip().rstrip("/")

    @property
    def harness_repository_url(self) -> str:
        base_url = self.harness_base_url_normalized
        account_identifier = self.harness_account_identifier.strip()
        org_identifier = self.harness_org_identifier.strip()
        project_identifier = self.harness_project_identifier.strip()

        if not base_url or not account_identifier or not org_identifier or not project_identifier:
            return ""

        return (
            f"{base_url}/ng/account/{quote(account_identifier, safe='')}"
            f"/module/code/orgs/{quote(org_identifier, safe='')}"
            f"/projects/{quote(project_identifier, safe='')}"
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()