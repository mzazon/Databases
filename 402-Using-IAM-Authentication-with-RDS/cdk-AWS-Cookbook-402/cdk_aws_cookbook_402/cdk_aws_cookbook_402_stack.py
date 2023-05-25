from constructs import Construct
from aws_cdk import (
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_s3_deployment,
    aws_rds as rds,
    aws_iam as iam,
    Stack,
    CfnOutput,
    RemovalPolicy
)


class CdkAwsCookbook402Stack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # create s3 bucket
        s3_Bucket = s3.Bucket(
            self,
            "AWS-Cookbook-Recipe-402",
            removal_policy=RemovalPolicy.DESTROY
        )

        aws_s3_deployment.BucketDeployment(
            self,
            'S3Deployment',
            destination_bucket=s3_Bucket,
            sources=[aws_s3_deployment.Source.asset("./s3_content")],
            retain_on_delete=False
        )

        isolated_subnets = ec2.SubnetConfiguration(
            name="PUBLIC",
            subnet_type=ec2.SubnetType.PUBLIC,
            cidr_mask=24
        )

        # create VPC
        vpc = ec2.Vpc(
            self,
            'AWS-Cookbook-VPC',
            cidr='10.10.0.0/23',
            subnet_configuration=[isolated_subnets]
        )


        rds_security_group = ec2.SecurityGroup(
            self,
            'rds_security_group',
            description='Security Group for the RDS Instance',
            allow_all_outbound=True,
            vpc=vpc
        )

        rds_instance = rds.DatabaseInstance(
            self,
            'DBInstance',
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_8_0
            ),
            instance_type=ec2.InstanceType("t3.medium"),
            vpc=vpc,
            database_name='AWSCookbookRecipe402',
            instance_identifier='awscookbookrecipe402',
            delete_automated_backups=True,
            deletion_protection=False,
            publicly_accessible=True,
            removal_policy=RemovalPolicy.DESTROY,
            allocated_storage=8,
            vpc_subnets=ec2.SubnetSelection(
                one_per_az=False,
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            security_groups=[rds_security_group]
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

        CfnOutput(
            self,
            'InstanceId',
            value=instance.instance_id
        )
        # -------- End EC2 Helper ---------

        rds_instance.secret.grant_read(instance)

        # allow connection from ec2 instance to DB
        rds_instance.connections.allow_from(
            instance.connections, ec2.Port.tcp(3306), "Ingress")

        s3_Bucket.grant_read(instance)

        # outputs

        CfnOutput(
            self,
            'VpcId',
            value=vpc.vpc_id
        )

        CfnOutput(
            self,
            'RdsSecurityGroup',
            value=rds_security_group.security_group_id
        )

        CfnOutput(
            self,
            'RdsDatabaseId',
            value=rds_instance.instance_identifier
        )

        CfnOutput(
            self,
            'RdsEndpoint',
            value=rds_instance.db_instance_endpoint_address
        )

        CfnOutput(
            self,
            'RdsPort',
            value=rds_instance.db_instance_endpoint_port
        )

        CfnOutput(
            self,
            'BucketName',
            value=s3_Bucket.bucket_name
        )

        isolated_subnets = vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC)

        CfnOutput(
            self,
            'IsolatedSubnets',
            value=', '.join(map(str, isolated_subnets.subnet_ids))
        )

        CfnOutput(
            self,
            'InstanceRoleName',
            value=iam_role.role_name
        )

        CfnOutput(
            self,
            'RdsSecretArn',
            value=rds_instance.secret.secret_full_arn
        )
