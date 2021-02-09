from aws_cdk import (
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_iam as iam,
    core,
)


class CdkAwsCookbook108Stack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        isolated_subnets = ec2.SubnetConfiguration(
            name="ISOLATED",
            subnet_type=ec2.SubnetType.ISOLATED,
            cidr_mask=24
        )

        # create VPC
        vpc = ec2.Vpc(
            self,
            'AWS-Cookbook-VPC-108',
            cidr='10.10.0.0/23',
            subnet_configuration=[isolated_subnets]
        )

        database_name = "AWSCookbookRecipe108"

        rds_cluster = rds.ServerlessCluster(
            self,
            'DBCluster',
            engine=rds.DatabaseClusterEngine.AURORA_POSTGRESQL,
            parameter_group=rds.ParameterGroup.from_parameter_group_name(self, 'ParameterGroup', 'default.aurora-postgresql10'),
            vpc=vpc,
            cluster_identifier='awscookbookrecipe108',
            default_database_name=database_name,
            # enable_data_api=True,
            deletion_protection=False,
            removal_policy=core.RemovalPolicy.DESTROY,
            vpc_subnets=ec2.SubnetSelection(
                one_per_az=False,
                subnet_type=ec2.SubnetType.ISOLATED
            ),
        )

        vpc.add_interface_endpoint(
            'RdsDataInterfaceEndpoint',
            service=ec2.InterfaceVpcEndpointAwsService('rds-data'),  # Find names with - aws ec2 describe-vpc-endpoint-services | jq '.ServiceNames'
            private_dns_enabled=True,
            subnets=ec2.SubnetSelection(
                one_per_az=False,
                subnet_type=ec2.SubnetType.ISOLATED
            ),
        )

        # -------- Begin EC2 Helper ---------
        vpc.add_interface_endpoint(
            'VPCSSMInterfaceEndpoint',
            service=ec2.InterfaceVpcEndpointAwsService('ssm'),  # Find names with - aws ec2 describe-vpc-endpoint-services | jq '.ServiceNames'
            private_dns_enabled=True,
            subnets=ec2.SubnetSelection(
                one_per_az=False,
                subnet_type=ec2.SubnetType.ISOLATED
            ),
        )

        vpc.add_interface_endpoint(
            'VPCEC2MessagesInterfaceEndpoint',
            service=ec2.InterfaceVpcEndpointAwsService('ec2messages'),  # Find names with - aws ec2 describe-vpc-endpoint-services | jq '.ServiceNames'
            private_dns_enabled=True,
            subnets=ec2.SubnetSelection(
                one_per_az=False,
                subnet_type=ec2.SubnetType.ISOLATED
            ),
        )

        vpc.add_interface_endpoint(
            'VPCSSMMessagesInterfaceEndpoint',
            service=ec2.InterfaceVpcEndpointAwsService('ssmmessages'),  # Find names with - aws ec2 describe-vpc-endpoint-services | jq '.ServiceNames'
            private_dns_enabled=True,
            subnets=ec2.SubnetSelection(
                one_per_az=False,
                subnet_type=ec2.SubnetType.ISOLATED
            ),
        )

        ami = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            edition=ec2.AmazonLinuxEdition.STANDARD,
            virtualization=ec2.AmazonLinuxVirt.HVM,
            storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE
        )

        iam_role = iam.Role(self, "InstanceSSM", assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"))

        iam_role.add_managed_policy(iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonEC2RoleforSSM"))

        instance = ec2.Instance(
            self,
            "Instance",
            instance_type=ec2.InstanceType("t3.nano"),
            machine_image=ami,
            role=iam_role,
            vpc=vpc,
        )

        core.CfnOutput(
            self,
            'InstanceID',
            value=instance.instance_id
        )
        # -------- End EC2 Helper ---------

        # outputs

        core.CfnOutput(
            self,
            'VPCId',
            value=vpc.vpc_id
        )

        core.CfnOutput(
            self,
            'SecretArn',
            value=rds_cluster.secret.secret_full_arn
        )

        core.CfnOutput(
            self,
            'ClusterArn',
            value=rds_cluster.cluster_arn
        )

        core.CfnOutput(
            self,
            'ClusterIdentifier',
            value=rds_cluster.cluster_identifier
        )

        core.CfnOutput(
            self,
            'DatabaseName',
            value=database_name
        )

        core.CfnOutput(
            self,
            'EC2RoleName',
            value=instance.role.role_name
        )
