# A reviewed release is optional while the account/foundation is being prepared.
variable "workload_release" {
  description = "Staging-only immutable workload release. References only; no secret values. Null creates the foundation alone."
  default     = null
  nullable    = true
  type = object({
    account_id      = string
    helper_image    = string
    certificate_arn = string
    public_hostname = string
    route53_zone_id = string
    etcd_endpoints  = list(string)
    browser_realms  = list(string)
    postgres = object({
      engine_version = string
      instance_class = string
    })
    services = map(object({
      image              = string
      source_revision    = string
      cpu                = number
      memory             = number
      bundle_secret_arn  = string
      bundle_version_id  = string
      bundle_files       = list(string)
      secret_kms_arns    = list(string)
      entrypoint         = list(string)
      command            = list(string)
      environment        = map(string)
      secret_environment = map(string)
      tls_server_name    = string
      health_path        = string
    }))
  })
  validation {
    condition = var.workload_release == null ? true : (
      can(regex("^[0-9]{12}$", var.workload_release.account_id)) &&
      toset(keys(var.workload_release.services)) == toset(["cp", "iam", "keycloak", "apisix"]) &&
      can(regex("^17\\.[0-9]+$", var.workload_release.postgres.engine_version)) &&
      can(regex("^${var.workload_release.account_id}\\.dkr\\.ecr\\.af-south-1\\.amazonaws\\.com/[a-z0-9_/-]+@sha256:[a-f0-9]{64}$", var.workload_release.helper_image)) &&
      length(var.workload_release.browser_realms) >= 1 && length(var.workload_release.browser_realms) <= 2 &&
      alltrue([for realm in var.workload_release.browser_realms : can(regex("^[A-Za-z0-9_-]+$", realm)) && lower(realm) != "master"]) &&
      length(var.workload_release.etcd_endpoints) == 3 &&
      length(toset(var.workload_release.etcd_endpoints)) == 3 &&
      alltrue([for endpoint in var.workload_release.etcd_endpoints : can(regex("^https://[A-Za-z0-9.-]+:2379$", endpoint))])
    )
    error_message = "Release requires a staging account, digest-pinned helper, PostgreSQL 17 minor version, all four services and three distinct authenticated TLS etcd endpoints."
  }
  validation {
    condition = var.workload_release == null ? true : alltrue([
      for name, service in var.workload_release.services :
      can(regex("^${var.workload_release.account_id}\\.dkr\\.ecr\\.af-south-1\\.amazonaws\\.com/[a-z0-9_/-]+@sha256:[a-f0-9]{64}$", service.image)) &&
      can(regex("^[a-f0-9]{40}$", service.source_revision)) &&
      contains([512, 1024, 2048, 4096], service.cpu) &&
      service.memory >= service.cpu * 2 && service.memory <= service.cpu * 8 && service.memory % 1024 == 0 &&
      startswith(service.bundle_secret_arn, "arn:aws:secretsmanager:af-south-1:${var.workload_release.account_id}:secret:") &&
      can(regex("^[A-Za-z0-9-]{32,64}$", service.bundle_version_id)) &&
      length(service.bundle_files) >= 3 && length(service.bundle_files) <= 64 &&
      length(toset(service.bundle_files)) == length(service.bundle_files) &&
      alltrue([for required in ["ca.pem", "service.pem", "service.key", "probe.pem", "probe.key"] : contains(service.bundle_files, required)]) &&
      alltrue([for file in service.bundle_files : can(regex("^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$", file)) && file != "runtime-helper"]) &&
      alltrue([for arn in service.secret_kms_arns : startswith(arn, "arn:aws:kms:af-south-1:${var.workload_release.account_id}:key/")]) &&
      can(regex("^[A-Za-z0-9.-]+$", service.tls_server_name)) &&
      can(regex("^/[A-Za-z0-9/_-]*$", service.health_path)) &&
      alltrue([for key, value in service.environment :
        !can(regex("(?i)(password|secret|token|database_url|aws_access|aws_secret)", key)) ||
        (endswith(key, "_FILE") && startswith(value, "/run/baobab/") && contains(service.bundle_files, trimprefix(value, "/run/baobab/")))
      ]) &&
      alltrue([for key, ref in service.secret_environment :
        contains(name == "cp" ? ["DATABASE_URL"] : name == "keycloak" ? ["KC_DB_USERNAME", "KC_DB_PASSWORD", "KC_BOOTSTRAP_ADMIN_PASSWORD"] : [], key) &&
        startswith(ref, "arn:aws:secretsmanager:af-south-1:${var.workload_release.account_id}:secret:") &&
        can(regex(":[^:]*::[A-Za-z0-9-]{32,64}$", ref))
      ])
    ])
    error_message = "Service releases must pin images/source/secret versions, use valid Fargate sizes and protected flat files, and carry same-account secret/KMS references. Plaintext credentials are forbidden."
  }
}

variable "activate_workloads" {
  description = "Start tasks only after secret bundles, database roles/migrations, private PKI and APISIX/etcd configuration are prepared."
  type        = bool
  default     = false
}
