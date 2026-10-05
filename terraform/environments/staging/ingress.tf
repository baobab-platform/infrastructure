resource "aws_lb" "browser" {
  count                      = var.workload_release == null ? 0 : 1
  name                       = "${local.name}-browser"
  internal                   = false
  load_balancer_type         = "application"
  subnets                    = local.public_subnet_ids
  security_groups            = [aws_security_group.alb_public.id]
  enable_deletion_protection = true
  drop_invalid_header_fields = true
}
resource "aws_lb_target_group" "apisix" {
  count       = var.workload_release == null ? 0 : 1
  name        = "${local.name}-apisix"
  port        = 9443
  protocol    = "HTTPS"
  target_type = "ip"
  vpc_id      = aws_vpc.staging.id
  health_check {
    protocol = "HTTPS"
    path     = "/healthz"
    matcher  = "200"
  }
}
resource "aws_lb_listener" "browser" {
  count             = var.workload_release == null ? 0 : 1
  load_balancer_arn = aws_lb.browser[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.workload_release.certificate_arn
  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "route denied"
      status_code  = "404"
    }
  }
}
resource "aws_lb_listener_rule" "browser" {
  count        = var.workload_release == null ? 0 : 1
  listener_arn = aws_lb_listener.browser[0].arn
  priority     = 100
  condition {
    host_header {
      values = [var.workload_release.public_hostname]
    }
  }
  # Only explicit browser routes enter APISIX. Internal authority and management
  # paths are never forwarded by the public listener, even if a gateway drifts.
  condition {
    path_pattern {
      values = concat([for realm in var.workload_release.browser_realms : "/realms/${realm}/*"], ["/resources/*", "/api/browser/*"])
    }
  }
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.apisix[0].arn
  }
}
resource "aws_route53_record" "browser" {
  count   = var.workload_release == null ? 0 : 1
  zone_id = var.workload_release.route53_zone_id
  name    = var.workload_release.public_hostname
  type    = "A"
  alias {
    name                   = aws_lb.browser[0].dns_name
    zone_id                = aws_lb.browser[0].zone_id
    evaluate_target_health = true
  }
}
output "browser_origin" {
  value = var.workload_release == null ? null : "https://${var.workload_release.public_hostname}"
}
