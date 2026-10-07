locals {
  name = "baobab-staging"

  subnet_sets = {
    public = {
      cidrs = var.public_subnet_cidrs
      zone  = "ingress"
    }
    application = {
      cidrs = var.application_subnet_cidrs
      zone  = "application"
    }
    data = {
      cidrs = var.data_subnet_cidrs
      zone  = "data"
    }
    management = {
      cidrs = var.management_subnet_cidrs
      zone  = "management"
    }
  }

  az_indexes = {
    for index in range(length(var.availability_zones)) : tostring(index) => index
  }

  endpoint_services = toset([
    "ecr.api",
    "ecr.dkr",
    "logs",
    "secretsmanager",
    "kms",
    "ssm",
    "ssmmessages",
    "ec2messages",
  ])
}

resource "aws_vpc" "staging" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name      = "${local.name}-vpc"
    TrustZone = "environment"
  }
}

resource "aws_internet_gateway" "staging" {
  vpc_id = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-igw"
    TrustZone = "ingress"
  }
}

resource "aws_subnet" "zone" {
  for_each = {
    for item in flatten([
      for class, config in local.subnet_sets : [
        for index, cidr in config.cidrs : {
          key   = "${class}-${index}"
          class = class
          zone  = config.zone
          cidr  = cidr
          az    = var.availability_zones[index]
        }
      ]
    ]) : item.key => item
  }

  vpc_id                  = aws_vpc.staging.id
  availability_zone       = each.value.az
  cidr_block              = each.value.cidr
  map_public_ip_on_launch = false

  tags = {
    Name      = "${local.name}-${each.value.class}-${replace(each.value.az, "af-south-1", "az")}"
    TrustZone = each.value.zone
  }
}

locals {
  public_subnet_ids      = [for index in range(length(var.availability_zones)) : aws_subnet.zone["public-${index}"].id]
  application_subnet_ids = [for index in range(length(var.availability_zones)) : aws_subnet.zone["application-${index}"].id]
  data_subnet_ids        = [for index in range(length(var.availability_zones)) : aws_subnet.zone["data-${index}"].id]
  management_subnet_ids  = [for index in range(length(var.availability_zones)) : aws_subnet.zone["management-${index}"].id]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.staging.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.staging.id
  }

  tags = {
    Name      = "${local.name}-public"
    TrustZone = "ingress"
  }
}

resource "aws_route_table_association" "public" {
  for_each = local.az_indexes

  subnet_id      = aws_subnet.zone["public-${each.value}"].id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name      = "${local.name}-nat"
    TrustZone = "ingress"
  }

  depends_on = [aws_internet_gateway.staging]
}

resource "aws_nat_gateway" "staging" {
  allocation_id = aws_eip.nat.id
  subnet_id     = local.public_subnet_ids[0]

  tags = {
    Name      = "${local.name}-nat"
    TrustZone = "ingress"
  }

  depends_on = [aws_internet_gateway.staging]
}

resource "aws_route_table" "application" {
  vpc_id = aws_vpc.staging.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.staging.id
  }

  tags = {
    Name      = "${local.name}-application"
    TrustZone = "application"
  }
}

resource "aws_route_table_association" "application" {
  for_each = local.az_indexes

  subnet_id      = aws_subnet.zone["application-${each.value}"].id
  route_table_id = aws_route_table.application.id
}

resource "aws_route_table" "data" {
  vpc_id = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-data"
    TrustZone = "data"
  }
}

resource "aws_route_table_association" "data" {
  for_each = local.az_indexes

  subnet_id      = aws_subnet.zone["data-${each.value}"].id
  route_table_id = aws_route_table.data.id
}

resource "aws_route_table" "management" {
  vpc_id = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-management"
    TrustZone = "management"
  }
}

resource "aws_route_table_association" "management" {
  for_each = local.az_indexes

  subnet_id      = aws_subnet.zone["management-${each.value}"].id
  route_table_id = aws_route_table.management.id
}

resource "aws_security_group" "alb_public" {
  name        = "${local.name}-alb-public"
  description = "Public HTTPS ingress only."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-alb-public"
    TrustZone = "ingress"
  }
}

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  for_each          = toset(var.public_ingress_cidrs)
  security_group_id = aws_security_group.alb_public.id
  cidr_ipv4         = each.value
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "Approved browser/API HTTPS ingress"
}

resource "aws_security_group" "alb_internal" {
  name        = "${local.name}-alb-internal"
  description = "Private TLS authority entry point; no CIDR ingress."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-alb-internal"
    TrustZone = "application"
  }
}

resource "aws_security_group" "apisix" {
  name        = "${local.name}-apisix"
  description = "Private APISIX traffic plane."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-apisix"
    TrustZone = "ingress"
  }
}

resource "aws_security_group" "cp" {
  name        = "${local.name}-cp"
  description = "Baobab Control Plane staging workload."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-cp"
    TrustZone = "application"
    Service   = "baobab-cp"
  }
}

resource "aws_security_group" "iam" {
  name        = "${local.name}-iam"
  description = "Baobab IAM governance/runtime staging workload."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-iam"
    TrustZone = "application"
    Service   = "baobab-iam"
  }
}

resource "aws_security_group" "pulse" {
  name        = "${local.name}-pulse"
  description = "Baobab Pulse intelligence staging workload."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-pulse"
    TrustZone = "application"
    Service   = "baobab-pulse"
  }
}

resource "aws_security_group" "keycloak" {
  name        = "${local.name}-keycloak"
  description = "Retained enterprise federation Keycloak runtime."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-keycloak"
    TrustZone = "application"
    Service   = "keycloak"
  }
}

resource "aws_security_group" "data" {
  name        = "${local.name}-data"
  description = "Private database boundary; ingress is service-SG specific."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-data"
    TrustZone = "data"
  }
}

resource "aws_security_group" "efs" {
  name        = "${local.name}-efs"
  description = "IAM staging durable ledger EFS."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-efs"
    TrustZone = "data"
  }
}

resource "aws_vpc_security_group_ingress_rule" "efs_from_iam" {
  security_group_id            = aws_security_group.efs.id
  referenced_security_group_id = aws_security_group.iam.id
  from_port                    = 2049
  to_port                      = 2049
  ip_protocol                  = "tcp"
  description                  = "Single-writer IAM ledger NFS"
}

resource "aws_vpc_security_group_egress_rule" "iam_to_efs" {
  security_group_id            = aws_security_group.iam.id
  referenced_security_group_id = aws_security_group.efs.id
  from_port                    = 2049
  to_port                      = 2049
  ip_protocol                  = "tcp"
  description                  = "IAM ledger persistence"
}

resource "aws_security_group" "endpoints" {
  name        = "${local.name}-endpoints"
  description = "Private AWS API VPC endpoints."
  vpc_id      = aws_vpc.staging.id

  tags = {
    Name      = "${local.name}-endpoints"
    TrustZone = "management"
  }
}

locals {
  endpoint_callers = {
    apisix   = aws_security_group.apisix.id
    cp       = aws_security_group.cp.id
    iam      = aws_security_group.iam.id
    pulse    = aws_security_group.pulse.id
    keycloak = aws_security_group.keycloak.id
  }

  external_https_callers = {
    iam      = aws_security_group.iam.id
    keycloak = aws_security_group.keycloak.id
  }
}

resource "aws_vpc_security_group_ingress_rule" "endpoint_https" {
  for_each = local.endpoint_callers

  security_group_id            = aws_security_group.endpoints.id
  referenced_security_group_id = each.value
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Private ${each.key} access to AWS APIs"
}

resource "aws_vpc_security_group_egress_rule" "workload_to_endpoints" {
  for_each = local.endpoint_callers

  security_group_id            = each.value
  referenced_security_group_id = aws_security_group.endpoints.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Private ${each.key} AWS API egress"
}

resource "aws_vpc_security_group_egress_rule" "federation_https" {
  for_each = local.external_https_callers

  security_group_id = each.value
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "HTTPS egress for approved federation/provider dependencies"
}

resource "aws_vpc_endpoint" "interface" {
  for_each = local.endpoint_services

  vpc_id              = aws_vpc.staging.id
  service_name        = "com.amazonaws.${var.aws_region}.${each.value}"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true
  subnet_ids          = local.management_subnet_ids
  security_group_ids  = [aws_security_group.endpoints.id]

  tags = {
    Name      = "${local.name}-${replace(each.value, ".", "-")}"
    TrustZone = "management"
  }
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.staging.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.application.id]

  tags = {
    Name      = "${local.name}-s3"
    TrustZone = "management"
  }
}

resource "aws_kms_key" "operations" {
  description             = "Baobab staging operational-session and evidence encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name      = "${local.name}-operations"
    TrustZone = "management"
  }
}

resource "aws_kms_alias" "operations" {
  name          = "alias/${local.name}-operations"
  target_key_id = aws_kms_key.operations.key_id
}

resource "aws_cloudwatch_log_group" "ecs_exec" {
  name              = "/baobab/staging/ecs-exec"
  retention_in_days = 30

  tags = {
    Name      = "${local.name}-ecs-exec"
    TrustZone = "management"
  }
}

resource "aws_ecs_cluster" "staging" {
  name = "${local.name}-ecs"

  configuration {
    execute_command_configuration {
      kms_key_id = aws_kms_key.operations.arn
      logging    = "OVERRIDE"

      log_configuration {
        cloud_watch_log_group_name     = aws_cloudwatch_log_group.ecs_exec.name
        cloud_watch_encryption_enabled = false
      }
    }
  }

  setting {
    name  = "containerInsights"
    value = "enhanced"
  }

  tags = {
    Name      = "${local.name}-ecs"
    TrustZone = "application"
  }
}

resource "aws_service_discovery_private_dns_namespace" "staging" {
  name        = var.cloud_map_namespace
  description = "Baobab staging private service discovery"
  vpc         = aws_vpc.staging.id

  tags = {
    Name      = var.cloud_map_namespace
    TrustZone = "application"
  }
}

resource "aws_kms_key" "iam_ledger" {
  description             = "Baobab IAM staging approval and replay evidence at rest"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name      = "${local.name}-iam-ledger"
    TrustZone = "data"
    Service   = "baobab-iam"
  }
}

resource "aws_efs_file_system" "iam_ledger" {
  encrypted        = true
  kms_key_id       = aws_kms_key.iam_ledger.arn
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = {
    Name      = "${local.name}-iam-ledger"
    TrustZone = "data"
    Service   = "baobab-iam"
  }
}

resource "aws_efs_mount_target" "iam_ledger" {
  for_each = local.az_indexes

  file_system_id  = aws_efs_file_system.iam_ledger.id
  subnet_id       = aws_subnet.zone["data-${each.value}"].id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "iam_ledger" {
  file_system_id = aws_efs_file_system.iam_ledger.id

  posix_user {
    gid = 65532
    uid = 65532
  }

  root_directory {
    path = "/baobab-iam"

    creation_info {
      owner_gid   = 65532
      owner_uid   = 65532
      permissions = "0700"
    }
  }

  tags = {
    Name    = "${local.name}-iam-ledger"
    Service = "baobab-iam"
  }
}

