# Baseline Terraform root module for baobab-platform infrastructure.
#
# The running stack is currently defined with Docker Compose (compose/).
# This module establishes the Terraform entry point that Foundation's
# infrastructure capability validates (terraform fmt, init -backend=false,
# validate). It declares no providers or resources yet; when the first
# provider is added, commit its .terraform.lock.hcl alongside it, which the
# Foundation reproducibility gate requires.
terraform {
  required_version = ">= 1.9.0"
}
