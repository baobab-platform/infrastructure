# terraform/environments/staging/providers.tf
provider "aws" {
  region = "af-south-1" # As required by ADR-Infra-0002

  default_tags {
    tags = {
      "baobab:environment"         = "staging"
      "baobab:managed-by"          = "terraform"
      "baobab:owner"               = "platform-eng"
      "baobab:cost-center"         = "platform-core-mp2c"
      "baobab:data-classification" = "confidential"
      "baobab:isolation-profile"  = "private-mesh"
      "baobab:repository"          = "baobab-platform/infrastructure"
      # Dynamically inject the cut tag into the AWS resource metadata array
      "baobab:release-version"     = var.github_release_tag 
    }
  }
}

variable "github_release_tag" {
  type        = string
  description = "The precise git tag orchestrating this infrastructure slice"
  default     = "untracked-dev-build"
}
