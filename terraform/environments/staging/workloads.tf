locals {
  workloads          = var.workload_release == null ? {} : var.workload_release.services
  workload_users     = { cp = 65532, iam = 65532, pulse = 1000, keycloak = 1000, apisix = 1000 }
  workload_app_ports = { cp = 8080, iam = 8443, pulse = 8000, keycloak = 8443, apisix = 9443 }
  workload_ports     = { cp = 8443, iam = 8443, pulse = 8443, keycloak = 8443, apisix = 9443 }
  task_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = var.workload_release == null ? "000000000000" : var.workload_release.account_id } }
    }]
  })
  secret_environment_arns = { for name, service in local.workloads : name => toset([
    for ref in values(service.secret_environment) : join(":", slice(split(":", ref), 0, 7))
  ]) }
  repositories = { for name, service in local.workloads : name => toset([
    for image in [service.image, var.workload_release.helper_image] :
    "arn:aws:ecr:af-south-1:${var.workload_release.account_id}:repository/${split("@", join("/", slice(split("/", image), 1, length(split("/", image)))))[0]}"
  ]) }
}
resource "aws_cloudwatch_log_group" "workload" {
  for_each          = local.workloads
  name              = "/baobab/staging/${each.key}"
  retention_in_days = 30
}
resource "aws_iam_role" "execution" {
  for_each           = local.workloads
  name               = "${local.name}-${each.key}-execution"
  assume_role_policy = local.task_trust
}
resource "aws_iam_role_policy" "execution" {
  for_each = local.workloads
  role     = aws_iam_role.execution[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Resource = local.repositories[each.key] },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.workload[each.key].arn}:*" }
      ], length(local.secret_environment_arns[each.key]) == 0 ? [] : [
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = local.secret_environment_arns[each.key] }
      ], length(each.value.secret_kms_arns) == 0 ? [] : [
      { Effect = "Allow", Action = ["kms:Decrypt"], Resource = each.value.secret_kms_arns, Condition = { StringEquals = { "kms:ViaService" = "secretsmanager.af-south-1.amazonaws.com" } } }
    ])
  })
}
resource "aws_iam_role" "workload" {
  for_each           = local.workloads
  name               = "${local.name}-${each.key}-task"
  assume_role_policy = local.task_trust
}
resource "aws_iam_role_policy" "workload" {
  for_each = local.workloads
  role     = aws_iam_role.workload[each.key].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = each.value.bundle_secret_arn },
      { Effect = "Allow", Action = ["ssmmessages:CreateControlChannel", "ssmmessages:CreateDataChannel", "ssmmessages:OpenControlChannel", "ssmmessages:OpenDataChannel"], Resource = "*" },
      { Effect = "Allow", Action = ["kms:Decrypt"], Resource = aws_kms_key.operations.arn },
      { Effect = "Allow", Action = ["logs:DescribeLogGroups"], Resource = "*" },
      { Effect = "Allow", Action = ["logs:DescribeLogStreams", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.ecs_exec.arn}:*" }
      ], length(each.value.secret_kms_arns) == 0 ? [] : [
      { Effect = "Allow", Action = ["kms:Decrypt"], Resource = each.value.secret_kms_arns, Condition = { StringEquals = { "kms:ViaService" = "secretsmanager.af-south-1.amazonaws.com" } } }
      ], each.key != "iam" ? [] : [
      { Effect = "Allow", Action = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"], Resource = aws_efs_file_system.iam_ledger.arn, Condition = { StringEquals = { "elasticfilesystem:AccessPointArn" = aws_efs_access_point.iam_ledger.arn }, Bool = { "aws:SecureTransport" = "true" } } }
    ])
  })
}
resource "aws_service_discovery_service" "workload" {
  for_each = local.workloads
  name     = each.key
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.staging.id
    routing_policy = "MULTIVALUE"
    dns_records {
      ttl  = 10
      type = "A"
    }
  }
  health_check_custom_config {
    failure_threshold = 1
  }
}
resource "aws_ecs_task_definition" "workload" {
  for_each                 = local.workloads
  family                   = "${local.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.execution[each.key].arn
  task_role_arn            = aws_iam_role.workload[each.key].arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  volume {
    name = "protected"
  }
  dynamic "volume" {
    for_each = each.key == "iam" ? [true] : []
    content {
      name = "ledger"
      efs_volume_configuration {
        file_system_id     = aws_efs_file_system.iam_ledger.id
        transit_encryption = "ENABLED"
        authorization_config {
          access_point_id = aws_efs_access_point.iam_ledger.id
          iam             = "ENABLED"
        }
      }
    }
  }
  container_definitions = jsonencode(concat([
    {
      name                   = "materialize", image = var.workload_release.helper_image, essential = false, user = "0:0", cpu = 128, memory = 256
      readonlyRootFilesystem = true
      command                = ["-mode=materialize", "-uid=${local.workload_users[each.key]}"]
      environment = [
        { name = "AWS_REGION", value = "af-south-1" },
        { name = "AWS_EC2_METADATA_DISABLED", value = "true" },
        { name = "BUNDLE_SECRET_ARN", value = each.value.bundle_secret_arn },
        { name = "BUNDLE_VERSION_ID", value = each.value.bundle_version_id },
        { name = "BUNDLE_FILES", value = jsonencode(each.value.bundle_files) }
      ]
      linuxParameters  = { capabilities = { drop = ["ALL"], add = ["CHOWN", "DAC_OVERRIDE", "FOWNER"] } }
      mountPoints      = [{ sourceVolume = "protected", containerPath = "/run/baobab", readOnly = false }]
      logConfiguration = { logDriver = "awslogs", options = { awslogs-group = aws_cloudwatch_log_group.workload[each.key].name, awslogs-region = "af-south-1", awslogs-stream-prefix = "init" } }
    },
    {
      name = each.key, image = each.value.image, essential = true, user = "${local.workload_users[each.key]}:${local.workload_users[each.key]}", cpu = each.value.cpu - 256, memory = each.value.memory - 512
      # ECS Exec's managed agent requires a writable root filesystem.
      readonlyRootFilesystem = false
      entryPoint             = each.value.entrypoint
      command                = each.value.command
      dependsOn              = [{ containerName = "materialize", condition = "SUCCESS" }]
      startTimeout           = 120
      stopTimeout            = 120
      environment            = [for name, value in each.value.environment : { name = name, value = value }]
      secrets                = [for name, ref in each.value.secret_environment : { name = name, valueFrom = ref }]
      linuxParameters        = { initProcessEnabled = true, capabilities = { drop = ["ALL"] } }
      portMappings           = [{ containerPort = local.workload_app_ports[each.key], protocol = "tcp" }]
      mountPoints = concat(
        [{ sourceVolume = "protected", containerPath = "/run/baobab", readOnly = true }],
        each.key == "iam" ? [{ sourceVolume = "ledger", containerPath = "/var/lib/baobab-iam", readOnly = false }] : [],
        each.key == "apisix" ? [{ sourceVolume = "protected", containerPath = "/usr/local/apisix/conf", readOnly = false }] : []
      )
      healthCheck = {
        command  = concat(["CMD", "/run/baobab/runtime-helper", "-mode=probe", "-url=https://127.0.0.1:${(each.key == "keycloak" ? 9000 : local.workload_ports[each.key])}${each.value.health_path}", "-server-name=${each.value.tls_server_name}"], ["-cert=/run/baobab/probe.pem", "-key=/run/baobab/probe.key"])
        interval = 30, timeout = 6, retries = 3, startPeriod = 120
      }
      logConfiguration = { logDriver = "awslogs", options = { awslogs-group = aws_cloudwatch_log_group.workload[each.key].name, awslogs-region = "af-south-1", awslogs-stream-prefix = "application" } }
    }
    ], contains(["cp", "pulse"], each.key) ? [
    {
      name                   = "private-tls", image = var.workload_release.helper_image, essential = true, user = "${local.workload_users[each.key]}:${local.workload_users[each.key]}", cpu = 128, memory = 256
      readonlyRootFilesystem = false
      command                = ["-mode=proxy", "-listen=:8443", "-upstream=http://127.0.0.1:${local.workload_app_ports[each.key]}"]
      dependsOn              = [{ containerName = "materialize", condition = "SUCCESS" }]
      stopTimeout            = 60
      linuxParameters        = { capabilities = { drop = ["ALL"] } }
      mountPoints            = [{ sourceVolume = "protected", containerPath = "/run/baobab", readOnly = true }]
      portMappings           = [{ containerPort = 8443, protocol = "tcp" }]
      healthCheck            = { command = ["CMD", "/runtime-helper", "-mode=probe", "-url=https://127.0.0.1:8443/_transport/health", "-server-name=${each.value.tls_server_name}", "-cert=/run/baobab/probe.pem", "-key=/run/baobab/probe.key"], interval = 30, timeout = 6, retries = 3, startPeriod = 30 }
      logConfiguration       = { logDriver = "awslogs", options = { awslogs-group = aws_cloudwatch_log_group.workload[each.key].name, awslogs-region = "af-south-1", awslogs-stream-prefix = "tls" } }
    }
  ]))
  tags = { Service = each.key, SourceRevision = each.value.source_revision }
}
resource "aws_ecs_service" "workload" {
  for_each                           = local.workloads
  name                               = "${local.name}-${each.key}"
  cluster                            = aws_ecs_cluster.staging.id
  task_definition                    = aws_ecs_task_definition.workload[each.key].arn
  desired_count                      = var.activate_workloads ? 1 : 0
  launch_type                        = "FARGATE"
  platform_version                   = "1.4.0"
  enable_execute_command             = true
  enable_ecs_managed_tags            = true
  propagate_tags                     = "TASK_DEFINITION"
  deployment_minimum_healthy_percent = each.key == "iam" ? 0 : 100
  deployment_maximum_percent         = each.key == "iam" ? 100 : 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = local.application_subnet_ids
    security_groups  = [local.workload_security_groups[each.key]]
    assign_public_ip = false
  }
  service_registries {
    registry_arn = aws_service_discovery_service.workload[each.key].arn
  }
  dynamic "load_balancer" {
    for_each = each.key == "apisix" ? [true] : []
    content {
      target_group_arn = aws_lb_target_group.apisix[0].arn
      container_name   = "apisix"
      container_port   = 9443
    }
  }
  lifecycle {
    precondition {
      condition     = !var.activate_workloads || var.etcd_security_group_id != null
      error_message = "Workload activation requires the approved durable etcd cluster boundary."
    }
  }
  depends_on = [aws_vpc_security_group_ingress_rule.workload_link, aws_vpc_security_group_egress_rule.workload_link, aws_efs_mount_target.iam_ledger, aws_efs_file_system_policy.iam_ledger, aws_lb_listener.browser, aws_iam_role_policy.execution, aws_iam_role_policy.workload]
}
resource "aws_vpc_security_group_egress_rule" "ecr_s3" {
  for_each          = local.workloads
  security_group_id = local.workload_security_groups[each.key]
  prefix_list_id    = aws_vpc_endpoint.s3.prefix_list_id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}
output "workload_services" {
  value = { for name, service in aws_ecs_service.workload : name => {
    service_name = service.name, task_definition = service.task_definition
    private_name = "${name}.${var.cloud_map_namespace}"
    image        = local.workloads[name].image
  } }
}
