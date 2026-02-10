"""Secrets Manager Component - Secure secret storage for Code Remote.

Creates AWS Secrets Manager secrets for:
- GEMINI_API_KEY for LLM analysis
- Other application secrets
"""

import pulumi
import pulumi_aws as aws


class SecretsComponent(pulumi.ComponentResource):
    """AWS Secrets Manager for application secrets."""

    def __init__(
        self,
        name: str,
        environment: str,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:security:Secrets", name, None, opts)

        self.tags = tags or {}
        self.environment = environment

        # Gemini API Key secret — shell only, value populated manually or via CI/CD:
        #   aws secretsmanager put-secret-value \
        #       --secret-id code-remote/{env}/gemini-api-key \
        #       --secret-string '<your-api-key>'
        self.gemini_api_key = aws.secretsmanager.Secret(
            f"{name}-gemini-api-key",
            name=f"code-remote/{environment}/gemini-api-key",
            description="Google Gemini API key for LLM-powered code analysis",
            tags={**self.tags, "Name": f"{name}-gemini-api-key"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Application secrets (database URLs, etc. for future use)
        self.app_secrets = aws.secretsmanager.Secret(
            f"{name}-app-secrets",
            name=f"code-remote/{environment}/app-secrets",
            description="Application secrets (database URLs, API keys, etc.)",
            tags={**self.tags, "Name": f"{name}-app-secrets"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "gemini_api_key_arn": self.gemini_api_key.arn,
                "app_secrets_arn": self.app_secrets.arn,
            }
        )
