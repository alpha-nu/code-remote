"""Frontend Infrastructure Component - S3 + CloudFront.

This module creates the infrastructure for hosting the React frontend:
- S3 bucket for static files (private)
- CloudFront distribution for CDN and HTTPS
- Origin Access Control for secure S3 access
"""

import json

import pulumi
import pulumi_aws as aws


class FrontendComponent(pulumi.ComponentResource):
    """S3 + CloudFront infrastructure for frontend hosting."""

    def __init__(
        self,
        name: str,
        environment: str,
        api_endpoint: pulumi.Input[str] | None = None,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        """
        Create frontend hosting infrastructure.

        Args:
            name: Resource name prefix
            environment: Environment name (dev, staging, prod)
            api_endpoint: Optional API endpoint URL for CORS
            tags: Common tags to apply
            opts: Pulumi resource options
        """
        super().__init__("coderemote:infrastructure:Frontend", name, None, opts)

        self.environment = environment
        self.tags = tags or {}
        child_opts = pulumi.ResourceOptions(parent=self)

        # =====================================================================
        # S3 Bucket - Static File Storage
        # =====================================================================
        self.bucket = aws.s3.BucketV2(
            f"{name}-bucket",
            bucket_prefix=f"code-remote-{environment}-frontend-",
            tags={**self.tags, "Name": f"{name}-bucket"},
            opts=child_opts,
        )

        # Block all public access (CloudFront will access via OAC)
        self.bucket_public_access_block = aws.s3.BucketPublicAccessBlock(
            f"{name}-bucket-public-access-block",
            bucket=self.bucket.id,
            block_public_acls=True,
            block_public_policy=True,
            ignore_public_acls=True,
            restrict_public_buckets=True,
            opts=child_opts,
        )

        # Enable versioning for rollback capability
        self.bucket_versioning = aws.s3.BucketVersioningV2(
            f"{name}-bucket-versioning",
            bucket=self.bucket.id,
            versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(
                status="Enabled" if environment == "prod" else "Suspended",
            ),
            opts=child_opts,
        )

        # =====================================================================
        # CloudFront Origin Access Control
        # =====================================================================
        self.oac = aws.cloudfront.OriginAccessControl(
            f"{name}-oac",
            name=f"code-remote-{environment}-frontend-oac",
            description=f"OAC for {environment} frontend",
            origin_access_control_origin_type="s3",
            signing_behavior="always",
            signing_protocol="sigv4",
            opts=child_opts,
        )

        # =====================================================================
        # CloudFront Distribution
        # =====================================================================

        # Cache policy for static assets
        cache_policy = self._get_cache_policy(environment)

        self.distribution = aws.cloudfront.Distribution(
            f"{name}-distribution",
            enabled=True,
            is_ipv6_enabled=True,
            comment=f"Code Remote {environment} frontend",
            default_root_object="index.html",
            price_class=self._get_price_class(environment),
            # Origins
            origins=[
                aws.cloudfront.DistributionOriginArgs(
                    domain_name=self.bucket.bucket_regional_domain_name,
                    origin_id="s3-frontend",
                    origin_access_control_id=self.oac.id,
                ),
            ],
            # Default cache behavior
            default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
                allowed_methods=["GET", "HEAD", "OPTIONS"],
                cached_methods=["GET", "HEAD"],
                target_origin_id="s3-frontend",
                viewer_protocol_policy="redirect-to-https",
                compress=True,
                # Use managed cache policy
                cache_policy_id=cache_policy,
                # No origin request policy needed for S3
            ),
            # Custom error responses for SPA routing
            custom_error_responses=[
                aws.cloudfront.DistributionCustomErrorResponseArgs(
                    error_code=403,
                    response_code=200,
                    response_page_path="/index.html",
                    error_caching_min_ttl=10,
                ),
                aws.cloudfront.DistributionCustomErrorResponseArgs(
                    error_code=404,
                    response_code=200,
                    response_page_path="/index.html",
                    error_caching_min_ttl=10,
                ),
            ],
            # Restrictions (no geo-restrictions)
            restrictions=aws.cloudfront.DistributionRestrictionsArgs(
                geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
                    restriction_type="none",
                ),
            ),
            # Use CloudFront default certificate (*.cloudfront.net)
            # For custom domain, add ACM certificate here
            viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
                cloudfront_default_certificate=True,
            ),
            tags={**self.tags, "Name": f"{name}-distribution"},
            opts=child_opts,
        )

        # =====================================================================
        # S3 Bucket Policy - Allow CloudFront Access
        # =====================================================================
        self.bucket_policy = aws.s3.BucketPolicy(
            f"{name}-bucket-policy",
            bucket=self.bucket.id,
            policy=pulumi.Output.all(self.bucket.arn, self.distribution.arn).apply(
                lambda args: self._create_bucket_policy(args[0], args[1])
            ),
            opts=pulumi.ResourceOptions(
                parent=self,
                depends_on=[self.bucket_public_access_block],
            ),
        )

        # Register outputs
        self.register_outputs(
            {
                "bucket_name": self.bucket.bucket,
                "bucket_arn": self.bucket.arn,
                "distribution_id": self.distribution.id,
                "distribution_domain": self.distribution.domain_name,
                "distribution_arn": self.distribution.arn,
            }
        )

    def _get_cache_policy(self, environment: str) -> str:
        """Get CloudFront managed cache policy ID."""
        # Managed-CachingOptimized policy
        # TTL: min 1s, default 86400s (1 day), max 31536000s (1 year)
        return "658327ea-f89d-4fab-a63d-7e88639e58f6"

    def _get_price_class(self, environment: str) -> str:
        """Get CloudFront price class based on environment."""
        if environment == "prod":
            # All edge locations for production
            return "PriceClass_All"
        else:
            # US, Canada, Europe only for dev/staging (cheaper)
            return "PriceClass_100"

    def _create_bucket_policy(self, bucket_arn: str, distribution_arn: str) -> str:
        """Create S3 bucket policy allowing CloudFront access."""
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowCloudFrontServicePrincipal",
                    "Effect": "Allow",
                    "Principal": {"Service": "cloudfront.amazonaws.com"},
                    "Action": "s3:GetObject",
                    "Resource": f"{bucket_arn}/*",
                    "Condition": {"StringEquals": {"AWS:SourceArn": distribution_arn}},
                }
            ],
        }
        return json.dumps(policy)
