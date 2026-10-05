terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 6.67.0"
    }
  }
}

provider "aws" {
  region              = var.aws_region
  allowed_account_ids = var.workload_release == null ? null : [var.workload_release.account_id]

  default_tags {
    tags = {
      Platform                     = "baobab"
      Environment                  = var.environment
      ManagedBy                    = "terraform"
      Repository                   = "baobab-platform/infrastructure"
      Owner                        = "baobab-platform"
      DataClassification           = "confidential"
      CostCentre                   = "platform"
      "baobab:environment"         = "staging"
      "baobab:managed-by"          = "terraform"
      "baobab:owner"               = "platform-eng"
      "baobab:cost-center"         = "platform-core-mp2c"
      "baobab:data-classification" = "confidential"
      "baobab:isolation-profile"   = "private-mesh"
      "baobab:repository"          = "baobab-platform/infrastructure"
      "baobab:release-version"     = var.github_release_tag
    }
  }
}


