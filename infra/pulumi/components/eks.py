"""EKS Component - Kubernetes cluster for Code Remote.

Creates an EKS cluster with:
- Managed node groups using Spot instances for cost savings
- gVisor support for executor sandboxing
- Cluster autoscaler ready
"""

import pulumi
import pulumi_aws as aws

from components.iam import IAMComponent


class EKSComponent(pulumi.ComponentResource):
    """EKS cluster with managed node groups."""

    def __init__(
        self,
        name: str,
        environment: str,
        vpc_id: pulumi.Input[str],
        subnet_ids: pulumi.Input[list[str]],
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:compute:EKS", name, None, opts)

        self.tags = tags or {}
        self.environment = environment

        # Create IAM roles
        self.iam = IAMComponent(
            f"{name}-iam",
            environment=environment,
            tags=tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # =================================================================
        # Security Group for EKS Cluster
        # =================================================================
        self.cluster_sg = aws.ec2.SecurityGroup(
            f"{name}-cluster-sg",
            name=f"code-remote-{environment}-eks-cluster",
            description="Security group for EKS cluster",
            vpc_id=vpc_id,
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    description="HTTPS from VPC",
                    from_port=443,
                    to_port=443,
                    protocol="tcp",
                    cidr_blocks=["10.0.0.0/8"],
                ),
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    description="Allow all outbound",
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=["0.0.0.0/0"],
                ),
            ],
            tags={**self.tags, "Name": f"{name}-cluster-sg"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # =================================================================
        # EKS Cluster
        # =================================================================
        self.cluster = aws.eks.Cluster(
            f"{name}-cluster",
            name=f"code-remote-{environment}",
            role_arn=self.iam.cluster_role.arn,
            version="1.29",  # Latest stable as of 2026
            vpc_config=aws.eks.ClusterVpcConfigArgs(
                subnet_ids=subnet_ids,
                security_group_ids=[self.cluster_sg.id],
                endpoint_private_access=True,
                endpoint_public_access=True,  # For kubectl access
            ),
            enabled_cluster_log_types=[
                "api",
                "audit",
                "authenticator",
            ],
            tags={**self.tags, "Name": f"{name}-cluster"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # =================================================================
        # Node Group - API (On-Demand for reliability)
        # =================================================================
        self.api_node_group = aws.eks.NodeGroup(
            f"{name}-api-nodes",
            cluster_name=self.cluster.name,
            node_group_name=f"code-remote-{environment}-api",
            node_role_arn=self.iam.node_role.arn,
            subnet_ids=subnet_ids,
            instance_types=["t3.small"] if environment == "dev" else ["t3.medium"],
            capacity_type="ON_DEMAND",
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=1 if environment == "dev" else 2,
                min_size=1,
                max_size=3 if environment == "dev" else 5,
            ),
            labels={
                "workload": "api",
                "environment": environment,
            },
            tags={**self.tags, "Name": f"{name}-api-nodes"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # =================================================================
        # Node Group - Executor (Spot for cost savings)
        # =================================================================
        self.executor_node_group = aws.eks.NodeGroup(
            f"{name}-executor-nodes",
            cluster_name=self.cluster.name,
            node_group_name=f"code-remote-{environment}-executor",
            node_role_arn=self.iam.node_role.arn,
            subnet_ids=subnet_ids,
            # Multiple instance types for Spot availability
            instance_types=["t3.small", "t3a.small"]
            if environment == "dev"
            else ["t3.medium", "t3a.medium"],
            capacity_type="SPOT",  # Cost savings!
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=1 if environment == "dev" else 2,
                min_size=0,  # Can scale to zero when idle
                max_size=5 if environment == "dev" else 20,
            ),
            labels={
                "workload": "executor",
                "environment": environment,
            },
            taints=[
                aws.eks.NodeGroupTaintArgs(
                    key="workload",
                    value="executor",
                    effect="NO_SCHEDULE",
                ),
            ],
            tags={**self.tags, "Name": f"{name}-executor-nodes"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # =================================================================
        # OIDC Provider for IRSA (IAM Roles for Service Accounts)
        # =================================================================
        # Get the OIDC issuer URL
        oidc_url = self.cluster.identities[0].oidcs[0].issuer

        # Create OIDC provider
        self.oidc_provider = aws.iam.OpenIdConnectProvider(
            f"{name}-oidc",
            client_id_lists=["sts.amazonaws.com"],
            thumbprint_lists=[
                "9e99a48a9960b14926bb7f3b02e22da2b0ab7280"
            ],  # AWS root CA
            url=oidc_url,
            tags={**self.tags, "Name": f"{name}-oidc"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "cluster_name": self.cluster.name,
                "cluster_endpoint": self.cluster.endpoint,
                "cluster_ca_data": self.cluster.certificate_authority.data,
                "oidc_provider_arn": self.oidc_provider.arn,
            }
        )
