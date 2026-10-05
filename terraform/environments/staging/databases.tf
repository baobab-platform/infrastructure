locals {
  database_owners = var.workload_release == null ? toset([]) : toset(["cp", "keycloak"])
}
resource "aws_kms_key" "database" {
  for_each                = local.database_owners
  description             = "Staging ${each.key} PostgreSQL storage and backups"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}
resource "aws_db_subnet_group" "workloads" {
  count      = var.workload_release == null ? 0 : 1
  name       = "${local.name}-postgres"
  subnet_ids = local.data_subnet_ids
}
resource "aws_security_group" "database" {
  for_each    = local.database_owners
  name        = "${local.name}-${each.key}-postgres"
  description = "Private service-owned PostgreSQL"
  vpc_id      = aws_vpc.staging.id
}
resource "aws_vpc_security_group_ingress_rule" "database" {
  for_each                     = local.database_owners
  security_group_id            = aws_security_group.database[each.key].id
  referenced_security_group_id = local.workload_security_groups[each.key]
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
resource "aws_vpc_security_group_egress_rule" "database" {
  for_each                     = local.database_owners
  security_group_id            = local.workload_security_groups[each.key]
  referenced_security_group_id = aws_security_group.database[each.key].id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}
resource "aws_db_parameter_group" "workloads" {
  count  = var.workload_release == null ? 0 : 1
  name   = "${local.name}-postgres17-tls"
  family = "postgres17"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}
resource "aws_db_instance" "workloads" {
  for_each                        = local.database_owners
  identifier                      = "${local.name}-${each.key}-postgres"
  engine                          = "postgres"
  engine_version                  = var.workload_release.postgres.engine_version
  instance_class                  = var.workload_release.postgres.instance_class
  allocated_storage               = 20
  max_allocated_storage           = 100
  storage_type                    = "gp3"
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.database[each.key].arn
  username                        = "platform_bootstrap"
  manage_master_user_password     = true
  db_name                         = each.key == "cp" ? "controlplane" : "keycloak"
  db_subnet_group_name            = aws_db_subnet_group.workloads[0].name
  vpc_security_group_ids          = [aws_security_group.database[each.key].id]
  parameter_group_name            = aws_db_parameter_group.workloads[0].name
  publicly_accessible             = false
  multi_az                        = true
  backup_retention_period         = 7
  copy_tags_to_snapshot           = true
  deletion_protection             = true
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${local.name}-${each.key}-final"
  auto_minor_version_upgrade      = false
  allow_major_version_upgrade     = false
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  lifecycle {
    prevent_destroy = true
  }
}
output "workload_databases" {
  description = "Bootstrap metadata only. Applications must use separate least-privilege database roles. Master secrets are not granted to application task roles."
  value = { for name, db in aws_db_instance.workloads : name => {
    endpoint          = db.address
    database          = db.db_name
    master_secret_arn = db.master_user_secret[0].secret_arn
  } }
}
