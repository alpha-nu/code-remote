"""VPC Component - Network foundation for Code Remote.

Creates a VPC with public and private subnets across multiple availability zones.
- Public subnets: For load balancers and NAT gateways
- Private subnets: For EKS nodes and application workloads
"""

import pulumi
import pulumi_aws as aws


class VPCComponent(pulumi.ComponentResource):
    """VPC with public/private subnets for EKS cluster."""

    def __init__(
        self,
        name: str,
        environment: str,
        cidr_block: str = "10.0.0.0/16",
        availability_zones: int = 2,
        tags: dict | None = None,
        opts: pulumi.ResourceOptions | None = None,
    ):
        super().__init__("coderemote:network:VPC", name, None, opts)

        self.tags = tags or {}
        self.environment = environment

        # Get available AZs in the region
        available_azs = aws.get_availability_zones(state="available")
        az_names = available_azs.names[:availability_zones]

        # Create VPC
        self.vpc = aws.ec2.Vpc(
            f"{name}-vpc",
            cidr_block=cidr_block,
            enable_dns_hostnames=True,
            enable_dns_support=True,
            tags={**self.tags, "Name": f"{name}-vpc"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Internet Gateway for public subnets
        self.igw = aws.ec2.InternetGateway(
            f"{name}-igw",
            vpc_id=self.vpc.id,
            tags={**self.tags, "Name": f"{name}-igw"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Create subnets
        self.public_subnets: list[aws.ec2.Subnet] = []
        self.private_subnets: list[aws.ec2.Subnet] = []
        self.nat_gateways: list[aws.ec2.NatGateway] = []

        for i, az in enumerate(az_names):
            # Public subnet (for ALB, NAT Gateway)
            public_subnet = aws.ec2.Subnet(
                f"{name}-public-{i}",
                vpc_id=self.vpc.id,
                cidr_block=f"10.0.{i * 16}.0/20",
                availability_zone=az,
                map_public_ip_on_launch=True,
                tags={
                    **self.tags,
                    "Name": f"{name}-public-{az}",
                    "kubernetes.io/role/elb": "1",  # For EKS ALB
                },
                opts=pulumi.ResourceOptions(parent=self),
            )
            self.public_subnets.append(public_subnet)

            # Private subnet (for EKS nodes)
            private_subnet = aws.ec2.Subnet(
                f"{name}-private-{i}",
                vpc_id=self.vpc.id,
                cidr_block=f"10.0.{i * 16 + 128}.0/20",
                availability_zone=az,
                tags={
                    **self.tags,
                    "Name": f"{name}-private-{az}",
                    "kubernetes.io/role/internal-elb": "1",  # For EKS internal ALB
                },
                opts=pulumi.ResourceOptions(parent=self),
            )
            self.private_subnets.append(private_subnet)

            # Elastic IP for NAT Gateway (only in non-dev for cost savings)
            if environment != "dev" or i == 0:
                eip = aws.ec2.Eip(
                    f"{name}-eip-{i}",
                    domain="vpc",
                    tags={**self.tags, "Name": f"{name}-nat-eip-{az}"},
                    opts=pulumi.ResourceOptions(parent=self),
                )

                # NAT Gateway (one per AZ for HA, or one for dev)
                nat = aws.ec2.NatGateway(
                    f"{name}-nat-{i}",
                    subnet_id=public_subnet.id,
                    allocation_id=eip.id,
                    tags={**self.tags, "Name": f"{name}-nat-{az}"},
                    opts=pulumi.ResourceOptions(parent=self, depends_on=[self.igw]),
                )
                self.nat_gateways.append(nat)

        # Route tables
        # Public route table - routes to Internet Gateway
        self.public_rt = aws.ec2.RouteTable(
            f"{name}-public-rt",
            vpc_id=self.vpc.id,
            routes=[
                aws.ec2.RouteTableRouteArgs(
                    cidr_block="0.0.0.0/0",
                    gateway_id=self.igw.id,
                ),
            ],
            tags={**self.tags, "Name": f"{name}-public-rt"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Associate public subnets with public route table
        for i, subnet in enumerate(self.public_subnets):
            aws.ec2.RouteTableAssociation(
                f"{name}-public-rta-{i}",
                subnet_id=subnet.id,
                route_table_id=self.public_rt.id,
                opts=pulumi.ResourceOptions(parent=self),
            )

        # Private route tables - route to NAT Gateway
        self.private_rts: list[aws.ec2.RouteTable] = []
        for i, subnet in enumerate(self.private_subnets):
            # In dev, all private subnets use the single NAT gateway
            nat_index = (
                0 if environment == "dev" else min(i, len(self.nat_gateways) - 1)
            )

            private_rt = aws.ec2.RouteTable(
                f"{name}-private-rt-{i}",
                vpc_id=self.vpc.id,
                routes=[
                    aws.ec2.RouteTableRouteArgs(
                        cidr_block="0.0.0.0/0",
                        nat_gateway_id=self.nat_gateways[nat_index].id,
                    ),
                ],
                tags={**self.tags, "Name": f"{name}-private-rt-{i}"},
                opts=pulumi.ResourceOptions(parent=self),
            )
            self.private_rts.append(private_rt)

            aws.ec2.RouteTableAssociation(
                f"{name}-private-rta-{i}",
                subnet_id=subnet.id,
                route_table_id=private_rt.id,
                opts=pulumi.ResourceOptions(parent=self),
            )

        # Export subnet IDs as outputs
        self.public_subnet_ids = pulumi.Output.all(
            *[s.id for s in self.public_subnets]
        ).apply(lambda ids: list(ids))

        self.private_subnet_ids = pulumi.Output.all(
            *[s.id for s in self.private_subnets]
        ).apply(lambda ids: list(ids))

        self.register_outputs(
            {
                "vpc_id": self.vpc.id,
                "public_subnet_ids": self.public_subnet_ids,
                "private_subnet_ids": self.private_subnet_ids,
            }
        )
