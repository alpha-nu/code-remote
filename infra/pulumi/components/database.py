"""Database Component - PostgreSQL for Code Remote.

Creates either:
- RDS PostgreSQL (dev) - Free tier eligible, simpler
- Aurora PostgreSQL Serverless v2 (staging/prod) - Auto-scaling, cost-effective

Uses the existing VPC private subnets for database placement.
"""

import json
import random
import string

import pulumi
import pulumi_aws as aws


class DatabaseComponent(pulumi.ComponentResource):
    """PostgreSQL database for Code Remote.

    Features:
    - Dev: RDS PostgreSQL db.t4g.micro (free tier eligible)
    - Staging/Prod: Aurora Serverless v2 (scales to near-zero)
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
        super().__init__("coderemote:database:PostgreSQL", name, None, opts)

        self.tags = tags or {}
        self.environment = environment

        # DB subnet group (uses private subnets)
        self.subnet_group = aws.rds.SubnetGroup(
            f"{name}-subnet-group",
            subnet_ids=subnet_ids,
            description=f"Subnet group for {name} database",
            tags={**self.tags, "Name": f"{name}-subnet-group"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Security group for PostgreSQL
        self.security_group = aws.ec2.SecurityGroup(
            f"{name}-sg",
            vpc_id=vpc_id,
            description="Security group for PostgreSQL",
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
        db_password_secret = aws.secretsmanager.Secret(
            f"{name}-db-password-secret",
            name=f"code-remote/{environment}/db-password",
            description="PostgreSQL master password",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Generate random password value
        password_chars = string.ascii_letters + string.digits
        generated_password = "".join(random.choices(password_chars, k=32))

        # Store password in Secrets Manager
        _db_password_value = aws.secretsmanager.SecretVersion(
            f"{name}-db-password-value",
            secret_id=db_password_secret.id,
            secret_string=generated_password,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Choose database type based on environment
        if environment == "dev":
            self._create_rds_instance(name, generated_password)
        else:
            self._create_aurora_cluster(name, generated_password)

        # Store full connection details in Secrets Manager
        self.connection_secret = aws.secretsmanager.Secret(
            f"{name}-connection-secret",
            name=f"code-remote/{environment}/db-connection",
            description="PostgreSQL connection details",
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Build connection string and store in secret
        connection_details = pulumi.Output.all(
            host=self.endpoint,
            port=self.port,
            database="coderemote",
            username="coderemote",
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
            host=self.endpoint,
            port=self.port,
            database="coderemote",
            username="coderemote",
            password=generated_password,
        ).apply(
            lambda args: f"postgresql+asyncpg://{args['username']}:{args['password']}@{args['host']}:{args['port']}/{args['database']}"
        )

        self.register_outputs(
            {
                "endpoint": self.endpoint,
                "port": self.port,
                "database_name": "coderemote",
                "connection_secret_arn": self.connection_secret.arn,
                "security_group_id": self.security_group.id,
            }
        )

    def _create_rds_instance(self, name: str, password: str) -> None:
        """Create a simple RDS PostgreSQL instance for dev (free tier eligible)."""

        # Parameter group for RDS PostgreSQL
        self.parameter_group = aws.rds.ParameterGroup(
            f"{name}-params",
            family="postgres16",
            description=f"Parameter group for {name}",
            parameters=[
                aws.rds.ParameterGroupParameterArgs(
                    name="rds.force_ssl",
                    value="1",
                ),
            ],
            tags=self.tags,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # RDS PostgreSQL instance (db.t4g.micro is free tier eligible)
        self.instance = aws.rds.Instance(
            f"{name}-instance",
            identifier=f"code-remote-{self.environment}",
            engine="postgres",
            engine_version="16.4",
            instance_class="db.t4g.micro",  # Free tier eligible
            allocated_storage=20,  # 20GB is free tier eligible
            storage_type="gp2",
            db_name="coderemote",
            username="coderemote",
            password=password,
            db_subnet_group_name=self.subnet_group.name,
            vpc_security_group_ids=[self.security_group.id],
            parameter_group_name=self.parameter_group.name,
            publicly_accessible=False,
            skip_final_snapshot=True,
            deletion_protection=False,
            backup_retention_period=1,  # Minimum for free tier
            storage_encrypted=True,
            tags={**self.tags, "Name": f"{name}-instance"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Set outputs
        self.endpoint = self.instance.address
        self.port = self.instance.port

    def _create_aurora_cluster(self, name: str, password: str) -> None:
        """Create Aurora PostgreSQL Serverless v2 cluster for staging/prod."""

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
            cluster_identifier=f"code-remote-{self.environment}",
            engine=aws.rds.EngineType.AURORA_POSTGRESQL,
            engine_mode="provisioned",  # Serverless v2 uses provisioned mode
            engine_version="16.4",
            database_name="coderemote",
            master_username="coderemote",
            master_password=password,
            db_subnet_group_name=self.subnet_group.name,
            vpc_security_group_ids=[self.security_group.id],
            db_cluster_parameter_group_name=self.cluster_parameter_group.name,
            storage_encrypted=True,
            skip_final_snapshot=self.environment != "prod",
            final_snapshot_identifier=f"code-remote-{self.environment}-final"
            if self.environment == "prod"
            else None,
            deletion_protection=self.environment == "prod",
            serverlessv2_scaling_configuration=aws.rds.ClusterServerlessv2ScalingConfigurationArgs(
                min_capacity=0.5,  # 0.5 ACU minimum (cheapest)
                max_capacity=16.0 if self.environment == "prod" else 4.0,
            ),
            tags={**self.tags, "Name": f"{name}-cluster"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Aurora Serverless v2 instance
        self.aurora_instance = aws.rds.ClusterInstance(
            f"{name}-aurora-instance",
            cluster_identifier=self.cluster.id,
            instance_class="db.serverless",
            engine=aws.rds.EngineType.AURORA_POSTGRESQL,
            engine_version=self.cluster.engine_version,
            publicly_accessible=False,
            db_subnet_group_name=self.subnet_group.name,
            tags={**self.tags, "Name": f"{name}-instance"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Set outputs
        self.endpoint = self.cluster.endpoint
        self.port = self.cluster.port
