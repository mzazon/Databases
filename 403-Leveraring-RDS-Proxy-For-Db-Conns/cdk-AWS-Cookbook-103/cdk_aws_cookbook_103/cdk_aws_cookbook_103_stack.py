from aws_cdk import (
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_s3_deployment,
    aws_iam as iam,
    aws_rds as rds,
    aws_logs as logs,
    aws_lambda,
    custom_resources,
    core,
)


class CdkAwsCookbook103Stack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # create s3 bucket
        s3_Bucket = s3.Bucket(
            self,
            "AWS-Cookbook-Recipe-103",
            removal_policy=core.RemovalPolicy.DESTROY
        )

        aws_s3_deployment.BucketDeployment(
            self,
            'S3Deployment',
            destination_bucket=s3_Bucket,
            sources=[aws_s3_deployment.Source.asset("./s3_content")],
            retain_on_delete=False
        )

        isolated_subnets = ec2.SubnetConfiguration(
            name="ISOLATED",
            subnet_type=ec2.SubnetType.ISOLATED,
            cidr_mask=24
        )

        # create VPC
        vpc = ec2.Vpc(
            self,
            'AWS-Cookbook-VPC-103',
            cidr='10.10.0.0/23',
            subnet_configuration=[isolated_subnets]
        )

        vpc.add_interface_endpoint(
            'VPCSecretsManagerInterfaceEndpoint',
            service=ec2.InterfaceVpcEndpointAwsService('secretsmanager'),  # Find names with - aws ec2 describe-vpc-endpoint-services | jq '.ServiceNames'
            private_dns_enabled=True,
            subnets=ec2.SubnetSelection(
                one_per_az=False,
                subnet_type=ec2.SubnetType.ISOLATED
            ),
        )

        vpc.add_gateway_endpoint(
            's3GateWayEndPoint',
            service=ec2.GatewayVpcEndpointAwsService('s3'),
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.ISOLATED)],
        )

        subnet_group = rds.SubnetGroup(
            self,
            'rds_subnet_group',
            description='VPC Subnet Group for RDS',
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                one_per_az=False,
                subnet_type=ec2.SubnetType.ISOLATED
            )
        )

        rds_security_group = ec2.SecurityGroup(
            self,
            'rds_security_group',
            description='Security Group for the RDS Instance',
            allow_all_outbound=True,
            vpc=vpc
        )

        db_name = 'AWSCookbookRecipe103'

        rds_instance = rds.DatabaseInstance(
            self,
            'DBInstance',
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.VER_5_7_26
            ),
            instance_type=ec2.InstanceType("m5.large"),
            vpc=vpc,
            multi_az=False,
            database_name=db_name,
            instance_identifier='awscookbook103db',
            delete_automated_backups=True,
            deletion_protection=False,
            removal_policy=core.RemovalPolicy.DESTROY,
            allocated_storage=8,
            subnet_group=subnet_group,
            security_groups=[rds_security_group]
        )

        # mkdir -p lambda-layers/sqlparse/python
        # cd layers/sqlparse/python
        # pip install sqlparse --target="."
        # cd ../../../

        # create Lambda Layer
        sqlparse = aws_lambda.LayerVersion(
            self,
            "sqlparse",
            code=aws_lambda.AssetCode('lambda-layers/sqlparse'),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description="sqlparse",
            license="https://github.com/andialbrecht/sqlparse/blob/master/LICENSE"
        )

        pymysql = aws_lambda.LayerVersion(
            self,
            "pymysql",
            code=aws_lambda.AssetCode('lambda-layers/pymysql'),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description="pymysql",
            license="MIT"
        )

        smartopen = aws_lambda.LayerVersion(
            self,
            "smartopen",
            code=aws_lambda.AssetCode('lambda-layers/smart_open'),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description="smartopen",
            license="MIT"
        )

        lambda_function = aws_lambda.Function(
            self,
            'LambdaRDS',
            code=aws_lambda.AssetCode("./mysql-lambda/"),
            handler="lambda_function.lambda_handler",
            environment={
                "DB_SECRET_ARN": rds_instance.secret.secret_arn,
                "S3_BUCKET": s3_Bucket.bucket_name
            },
            layers=[sqlparse, pymysql, smartopen],
            memory_size=1024,
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            timeout=core.Duration.seconds(600),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.ISOLATED
            )
        )

        rds_instance.secret.grant_read(lambda_function)

        rds_instance.connections.allow_from(
            lambda_function.connections, ec2.Port.tcp(3306), "Ingress")

        s3_Bucket.grant_read(lambda_function)

        db_app_security_group = ec2.SecurityGroup(
            self,
            'db_app_security_group',
            description='Security Group for the DB App',
            allow_all_outbound=True,
            vpc=vpc
        )

        db_app_lambda_function = aws_lambda.Function(
            self,
            'LambdaApp',
            code=aws_lambda.AssetCode("./db-app-lambda/"),
            handler="lambda_function.lambda_handler",
            environment={
                "DB_HOST": rds_instance.db_instance_endpoint_address,
            },
            layers=[pymysql],
            memory_size=1024,
            security_groups=[db_app_security_group],
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            timeout=core.Duration.seconds(600),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.ISOLATED
            )
        )

        create_params = {
            "FunctionName": lambda_function.function_arn,
        }

        on_create = custom_resources.AwsSdkCall(
            action='invoke',
            service='Lambda',
            parameters=create_params,
            physical_resource_id=custom_resources.PhysicalResourceId.of('LambdaRDS')
        )

        policy_statement = iam.PolicyStatement(
            actions=["lambda:InvokeFunction"],
            effect=iam.Effect.ALLOW,
            resources=[lambda_function.function_arn],
        )

        policy = custom_resources.AwsCustomResourcePolicy.from_statements(
            statements=[policy_statement]
        )

        custom_resources.AwsCustomResource(
            self,
            'CustomResource',
            policy=policy,
            on_create=on_create,
            log_retention=logs.RetentionDays.TWO_WEEKS
        )

        # outputs

        core.CfnOutput(
            self,
            'VPCId',
            value=vpc.vpc_id
        )

        core.CfnOutput(
            self,
            'PyMysqlLambdaLayerArn',
            value=pymysql.layer_version_arn
        )

        core.CfnOutput(
            self,
            'RdsDatabaseId',
            value=rds_instance.instance_identifier
        )

        core.CfnOutput(
            self,
            'RdsSecurityGroup',
            value=rds_security_group.security_group_id
        )

        core.CfnOutput(
            self,
            'DbName',
            value=db_name
        )

        core.CfnOutput(
            self,
            'RdsSecretArn',
            value=rds_instance.secret.secret_full_arn
        )

        core.CfnOutput(
            self,
            'RdsEndpoint',
            value=rds_instance.db_instance_endpoint_address
        )

        core.CfnOutput(
            self,
            'RdsPort',
            value=rds_instance.db_instance_endpoint_port
        )

        isolated_subnets = vpc.select_subnets(subnet_type=ec2.SubnetType.ISOLATED)

        core.CfnOutput(
            self,
            'IsolatedSubnets',
            value=', '.join(map(str, isolated_subnets.subnet_ids))
        )

        core.CfnOutput(
            self,
            'DbAppFunctionRoleName',
            value=db_app_lambda_function.role.role_name
        )

        core.CfnOutput(
            self,
            'DbAppFunctionArn',
            value=db_app_lambda_function.function_arn
        )

        core.CfnOutput(
            self,
            'DbAppFunctionName',
            value=db_app_lambda_function.function_name
        )

        core.CfnOutput(
            self,
            'S3BucketName',
            value=s3_Bucket.bucket_name
        )
        core.CfnOutput(
            self,
            'DbAppFunctionSgId',
            value=db_app_security_group.security_group_id
        )
