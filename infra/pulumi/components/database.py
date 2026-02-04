"""Database Component - Aurora PostgreSQL Serverless v2.

Creates an Aurora PostgreSQL Serverless v2 cluster for snippet persistence.
Uses the existing VPC private subnets for database placement.
"""

import json

import pulumi
import pulumi_aws as aws


class DatabaseComponent(pulumi.ComponentResource):
    """Aurora PostgreSQL Serverless v2 for Code Remote.

    Features:
    - Serverless v2 (scales to near-zero)
    - Private subnet placement
    - Security group restricted to VPC
    - Secrets Manager for credentials
    """

    def __init__(
        self,
        name: str,
        environment: str,
        vpc_id: pulumi.Input[str],
        subnet_ids: pulumi.Input[list[str]],
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:database:Aurora", name, None, opts)

        self.tags = tags or {}
        self.environment = environment

        # DB subnet group (uses private subnets)
        self.subnet_group = aws.rds.SubnetGroup(
            f"{name}-subnet-group",
            subnet_ids=subnet_ids,
            description=f"Subnet group for {name} Aurora cluster",
            tags={**self.tags, "Name": f"{name}-subnet-group"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Security group for Aurora
        self.security_group = aws.ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Security group for Aurora PostgreSQL",
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    protocol="tcp",
                    from_port=5432,
                    to_port=5432,
                    cidr_blocks=["10.0.0.0/8"],  # Allow from VPC
                    description="PostgreSQL from VPC",
                ),
            ],
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    protocol="-1",
                    from_port=0,
                    to_port=0,
                    cidr_blocks=["0.0.0.0/0"],
                    description="Allow all outbound",
                ),
            ],
            tags={**self.tags, "Name": f"{name}-sg"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Generate a random password for the database
        db_password = aws.secretsmanager.Secret(
            f"{name}-db-password-secret",
            name=f"code-remote/{environment}/db-password",
            description="Aurora PostgreSQL master password",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Generate random password value
        import random
        import string

        password_chars = string.ascii_letters + string.digits
        generated_password = "".join(random.choices(password_chars, k=32))

        # Store password in Secrets Manager (assigned to _ as we only need the side effect)
        _db_password_value = aws.secretsmanager.SecretVersion(
            f"{name}-db-password-value",
            secret_id=db_password.id,
            secret_string=generated_password,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Aurora cluster parameter group
        self.cluster_parameter_group = aws.rds.ClusterParameterGroup(
            f"{name}-cluster-params",
            family="aurora-postgresql16",
            description=f"Cluster parameters for {name}",
            parameters=[
                aws.rds.ClusterParameterGroupParameterArgs(
                    name="rds.force_ssl",
                    value="1",
                ),
            ],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Aurora Serverless v2 cluster
        self.cluster = aws.rds.Cluster(
            f"{name}-cluster",
            cluster_identifier=f"code-remote-{environment}",
            engine=aws.rds.EngineType.AURORA_POSTGRESQL,
            engine_mode="provisioned",  # Serverless v2 uses provisioned mode
            engine_version="16.4",  # PostgreSQL 16
            database_name="coderemote",
            master_username="coderemote",
            master_password=generated_password,
            db_subnet_group_name=self.subnet_group.name,
            vpc_security_group_ids=[self.security_group.id],
            db_cluster_parameter_group_name=self.cluster_parameter_group.name,
            storage_encrypted=True,
            skip_final_snapshot=environment == "dev",
            final_snapshot_identifier=f"code-remote-{environment}-final"
            if environment != "dev"
            else None,
            deletion_protection=environment == "prod",
            serverlessv2_scaling_configuration=aws.rds.ClusterServerlessv2ScalingConfigurationArgs(
                min_capacity=0.5,  # 0.5 ACU minimum (cheapest)
                max_capacity=4.0 if environment == "dev" else 16.0,
            ),
            tags={**self.tags, "Name": f"{name}-cluster"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Aurora Serverless v2 instance
        self.instance = aws.rds.ClusterInstance(
            f"{name}-instance",
            cluster_identifier=self.cluster.id,
            instance_class="db.serverless",
            engine=aws.rds.EngineType.AURORA_POSTGRESQL,
            engine_version=self.cluster.engine_version,
            publicly_accessible=False,
            db_subnet_group_name=self.subnet_group.name,
            tags={**self.tags, "Name": f"{name}-instance"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Store full connection details in Secrets Manager
        self.connection_secret = aws.secretsmanager.Secret(
            f"{name}-connection-secret",
            name=f"code-remote/{environment}/db-connection",
            description="Aurora PostgreSQL connection details",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Build connection string and store in secret
        connection_details = pulumi.Output.all(
            host=self.cluster.endpoint,
            port=self.cluster.port,
            database=self.cluster.database_name,
            username=self.cluster.master_username,
            password=generated_password,
        ).apply(
            lambda args: json.dumps(
                {
                    "host": args["host"],
                    "port": args["port"],
                    "database": args["database"],
                    "username": args["username"],
                    "password": args["password"],
                    "url": f"postgresql+asyncpg://{args['username']}:{args['password']}@{args['host']}:{args['port']}/{args['database']}",
                }
            )
        )

        self.connection_secret_version = aws.secretsmanager.SecretVersion(
            f"{name}-connection-value",
            secret_id=self.connection_secret.id,
            secret_string=connection_details,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Database URL for application config
        self.database_url = pulumi.Output.all(
            host=self.cluster.endpoint,
            port=self.cluster.port,
            database=self.cluster.database_name,
            username=self.cluster.master_username,
            password=generated_password,
        ).apply(
            lambda args: f"postgresql+asyncpg://{args['username']}:{args['password']}@{args['host']}:{args['port']}/{args['database']}"
        )

        self.register_outputs(
            {
                "cluster_endpoint": self.cluster.endpoint,
                "cluster_port": self.cluster.port,
                "database_name": self.cluster.database_name,
                "connection_secret_arn": self.connection_secret.arn,
                "security_group_id": self.security_group.id,
            }
        )
