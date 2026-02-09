"""Cognito Component - Authentication for Code Remote.

Creates AWS Cognito User Pool for user authentication.
Matches the frontend Amplify configuration.
"""

import pulumi
import pulumi_aws as aws


class CognitoComponent(pulumi.ComponentResource):
    """AWS Cognito User Pool for authentication."""

    def __init__(
        self,
        name: str,
        environment: str,
        frontend_url: pulumi.Input[str] | None = None,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:auth:Cognito", name, None, opts)

        self.tags = tags or {}
        self.environment = environment
        self.frontend_url = frontend_url

        # User Pool
        self.user_pool = aws.cognito.UserPool(
            f"{name}-user-pool",
            name=f"code-remote-{environment}",
            # Username configuration
            username_attributes=["email"],
            auto_verified_attributes=["email"],
            # Password policy
            password_policy=aws.cognito.UserPoolPasswordPolicyArgs(
                minimum_length=8,
                require_lowercase=True,
                require_numbers=True,
                require_symbols=False,
                require_uppercase=True,
            ),
            # Account recovery
            account_recovery_setting=aws.cognito.UserPoolAccountRecoverySettingArgs(
                recovery_mechanisms=[
                    aws.cognito.UserPoolAccountRecoverySettingRecoveryMechanismArgs(
                        name="verified_email",
                        priority=1,
                    ),
                ],
            ),
            # Email configuration (use Cognito default for simplicity)
            email_configuration=aws.cognito.UserPoolEmailConfigurationArgs(
                email_sending_account="COGNITO_DEFAULT",
            ),
            # MFA (optional, off by default)
            mfa_configuration="OFF",
            # Schema attributes
            schemas=[
                aws.cognito.UserPoolSchemaArgs(
                    name="email",
                    attribute_data_type="String",
                    required=True,
                    mutable=True,
                    string_attribute_constraints=aws.cognito.UserPoolSchemaStringAttributeConstraintsArgs(
                        min_length="1",
                        max_length="256",
                    ),
                ),
            ],
            tags={**self.tags, "Name": f"{name}-user-pool"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Build callback URLs list
        # Always include localhost for local development
        # The frontend_url is a Pulumi Output, so we need to handle it properly
        def build_callback_urls(frontend_url: str | None) -> list[str]:
            urls = ["http://localhost:5173"]
            if frontend_url:
                urls.append(frontend_url)
            return urls

        if self.frontend_url:
            callback_urls = pulumi.Output.all(self.frontend_url).apply(
                lambda args: build_callback_urls(args[0])
            )
            logout_urls = callback_urls  # Same URLs for both
        else:
            callback_urls = ["http://localhost:5173"]
            logout_urls = ["http://localhost:5173"]

        # User Pool Client (for frontend)
        self.user_pool_client = aws.cognito.UserPoolClient(
            f"{name}-client",
            name=f"code-remote-{environment}-web",
            user_pool_id=self.user_pool.id,
            # No client secret for public web app
            generate_secret=False,
            # Auth flows
            explicit_auth_flows=[
                "ALLOW_USER_SRP_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
            ],
            # OAuth configuration for hosted UI / redirect flows
            allowed_oauth_flows=["code"],
            allowed_oauth_flows_user_pool_client=True,
            allowed_oauth_scopes=["email", "openid", "profile"],
            callback_urls=callback_urls,
            logout_urls=logout_urls,
            supported_identity_providers=["COGNITO"],
            # Token validity
            access_token_validity=1,  # 1 hour
            id_token_validity=1,  # 1 hour
            refresh_token_validity=30,  # 30 days
            token_validity_units=aws.cognito.UserPoolClientTokenValidityUnitsArgs(
                access_token="hours",
                id_token="hours",
                refresh_token="days",
            ),
            # Prevent user existence errors (security)
            prevent_user_existence_errors="ENABLED",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # User Pool Domain (for hosted UI, optional)
        self.user_pool_domain = aws.cognito.UserPoolDomain(
            f"{name}-domain",
            domain=f"code-remote-{environment}",
            user_pool_id=self.user_pool.id,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "user_pool_id": self.user_pool.id,
                "user_pool_client_id": self.user_pool_client.id,
                "user_pool_endpoint": self.user_pool.endpoint,
                "user_pool_domain": self.user_pool_domain.domain,
            }
        )
