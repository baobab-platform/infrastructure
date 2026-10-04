output "vpc_id" {
  value       = aws_vpc.staging.id
  description = "Staging VPC ID."
}

output "public_subnet_ids" {
  value       = local.public_subnet_ids
  description = "Ingress subnet IDs."
}

output "application_subnet_ids" {
  value       = local.application_subnet_ids
  description = "Private application subnet IDs."
}

output "data_subnet_ids" {
  value       = local.data_subnet_ids
  description = "Private data subnet IDs."
}

output "ecs_cluster_arn" {
  value       = aws_ecs_cluster.staging.arn
  description = "Staging ECS/Fargate cluster ARN."
}

output "cloud_map_namespace_id" {
  value       = aws_service_discovery_private_dns_namespace.staging.id
  description = "Private service-discovery namespace."
}

output "service_security_groups" {
  value = {
    public_alb  = aws_security_group.alb_public.id
    internal_alb = aws_security_group.alb_internal.id
    apisix      = aws_security_group.apisix.id
    cp          = aws_security_group.cp.id
    iam         = aws_security_group.iam.id
    keycloak    = aws_security_group.keycloak.id
    data        = aws_security_group.data.id
    efs         = aws_security_group.efs.id
  }
  description = "Security-group identities used for explicit source-to-destination rules."
}

output "iam_ledger_file_system_id" {
  value       = aws_efs_file_system.iam_ledger.id
  description = "Encrypted EFS filesystem used by the single-writer staging IAM ledger."
}

output "iam_ledger_access_point_id" {
  value       = aws_efs_access_point.iam_ledger.id
  description = "EFS access point for the IAM ledger."
}
