locals {
  workload_security_groups = {
    apisix   = aws_security_group.apisix.id
    cp       = aws_security_group.cp.id
    iam      = aws_security_group.iam.id
    keycloak = aws_security_group.keycloak.id
  }
  workload_links = var.workload_release == null ? {} : {
    alb_apisix      = { source = aws_security_group.alb_public.id, destination = aws_security_group.apisix.id, port = 9443 }
    apisix_cp       = { source = aws_security_group.apisix.id, destination = aws_security_group.cp.id, port = 8443 }
    apisix_keycloak = { source = aws_security_group.apisix.id, destination = aws_security_group.keycloak.id, port = 8443 }
    iam_cp          = { source = aws_security_group.iam.id, destination = aws_security_group.cp.id, port = 8443 }
    cp_iam          = { source = aws_security_group.cp.id, destination = aws_security_group.iam.id, port = 8443 }
    keycloak_iam    = { source = aws_security_group.keycloak.id, destination = aws_security_group.iam.id, port = 8443 }
    iam_keycloak    = { source = aws_security_group.iam.id, destination = aws_security_group.keycloak.id, port = 8443 }
  }
}
resource "aws_vpc_security_group_ingress_rule" "workload_link" {
  for_each                     = local.workload_links
  security_group_id            = each.value.destination
  referenced_security_group_id = each.value.source
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
}
resource "aws_vpc_security_group_egress_rule" "workload_link" {
  for_each                     = local.workload_links
  security_group_id            = each.value.source
  referenced_security_group_id = each.value.destination
  ip_protocol                  = "tcp"
  from_port                    = each.value.port
  to_port                      = each.value.port
}
# etcd is a separate approved durable management-plane deployment, not an
# ephemeral Fargate sidecar. Only its SG identity is admitted here.
variable "etcd_security_group_id" {
  description = "Same-VPC approved durable etcd cluster SG; required for workload activation."
  type        = string
  default     = null
}
resource "aws_vpc_security_group_egress_rule" "apisix_etcd" {
  count                        = var.workload_release != null && var.etcd_security_group_id != null ? 1 : 0
  security_group_id            = aws_security_group.apisix.id
  referenced_security_group_id = var.etcd_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 2379
  to_port                      = 2379
}
resource "aws_vpc_security_group_ingress_rule" "etcd_apisix" {
  count                        = var.workload_release != null && var.etcd_security_group_id != null ? 1 : 0
  security_group_id            = var.etcd_security_group_id
  referenced_security_group_id = aws_security_group.apisix.id
  ip_protocol                  = "tcp"
  from_port                    = 2379
  to_port                      = 2379
}
