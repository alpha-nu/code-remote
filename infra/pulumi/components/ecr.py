"""ECR Component - Container Registry for Code Remote.

Creates ECR repository for the API service container image.
"""

import pulumi
import pulumi_aws as aws


class ECRComponent(pulumi.ComponentResource):
    """ECR repository for container images."""

    def __init__(
        self,
        name: str,
        environment: str,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:container:ECR", name, None, opts)

        self.tags = tags or {}
        self.environment = environment

        # API repository
        self.api_repository = aws.ecr.Repository(
            f"{name}-api",
            name=f"code-remote-{environment}-api",
            image_tag_mutability="MUTABLE",
            image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
                scan_on_push=True,
            ),
            tags={**self.tags, "Name": f"{name}-api"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Lifecycle policy to limit image count and reduce costs
        lifecycle_policy = """{
            "rules": [
                {
                    "rulePriority": 1,
                    "description": "Keep last 10 images",
                    "selection": {
                        "tagStatus": "any",
                        "countType": "imageCountMoreThan",
                        "countNumber": 10
                    },
                    "action": {
                        "type": "expire"
                    }
                }
            ]
        }"""

        aws.ecr.LifecyclePolicy(
            f"{name}-api-lifecycle",
            repository=self.api_repository.name,
            policy=lifecycle_policy,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "api_repository_url": self.api_repository.repository_url,
            }
        )
