"""IAM Component - Roles and policies for EKS.

Creates IAM roles for:
- EKS cluster (control plane)
- EKS node groups (worker nodes)
- Pod-level IAM (IRSA) for secrets access
"""

import json

import pulumi
import pulumi_aws as aws


class IAMComponent(pulumi.ComponentResource):
    """IAM roles and policies for EKS cluster."""

    def __init__(
        self,
        name: str,
        environment: str,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:iam:EKSRoles", name, None, opts)

        self.tags = tags or {}
        self.environment = environment

        # =================================================================
        # EKS Cluster Role
        # =================================================================
        eks_assume_role_policy = json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "eks.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        )

        self.cluster_role = aws.iam.Role(
            f"{name}-cluster-role",
            name=f"code-remote-{environment}-eks-cluster",
            assume_role_policy=eks_assume_role_policy,
            tags={**self.tags, "Name": f"{name}-cluster-role"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Attach required policies for EKS cluster
        aws.iam.RolePolicyAttachment(
            f"{name}-cluster-policy",
            role=self.cluster_role.name,
            policy_arn="arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # =================================================================
        # EKS Node Group Role
        # =================================================================
        ec2_assume_role_policy = json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "ec2.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        )

        self.node_role = aws.iam.Role(
            f"{name}-node-role",
            name=f"code-remote-{environment}-eks-node",
            assume_role_policy=ec2_assume_role_policy,
            tags={**self.tags, "Name": f"{name}-node-role"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Attach required policies for EKS nodes
        node_policies = [
            "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
            "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
            "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
        ]

        for i, policy_arn in enumerate(node_policies):
            aws.iam.RolePolicyAttachment(
                f"{name}-node-policy-{i}",
                role=self.node_role.name,
                policy_arn=policy_arn,
                opts=pulumi.ResourceOptions(parent=self),
            )

        # =================================================================
        # Secrets Access Policy (for pods to read secrets)
        # =================================================================
        self.secrets_policy = aws.iam.Policy(
            f"{name}-secrets-policy",
            name=f"code-remote-{environment}-secrets-access",
            description="Allow EKS pods to read application secrets",
            policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "secretsmanager:GetSecretValue",
                                "secretsmanager:DescribeSecret",
                            ],
                            "Resource": f"arn:aws:secretsmanager:*:*:secret:code-remote/{environment}/*",
                        }
                    ],
                }
            ),
            tags={**self.tags, "Name": f"{name}-secrets-policy"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Attach secrets policy to node role (simple approach)
        # For production, use IRSA (IAM Roles for Service Accounts)
        aws.iam.RolePolicyAttachment(
            f"{name}-node-secrets-policy",
            role=self.node_role.name,
            policy_arn=self.secrets_policy.arn,
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs(
            {
                "cluster_role_arn": self.cluster_role.arn,
                "node_role_arn": self.node_role.arn,
                "secrets_policy_arn": self.secrets_policy.arn,
            }
        )
