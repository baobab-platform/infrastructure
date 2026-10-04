terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.66"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Platform           = "baobab"
      Environment        = var.environment
      ManagedBy          = "terraform"
      Repository         = "baobab-platform/infrastructure"
      Owner              = "baobab-platform"
      DataClassification = "confidential"
      CostCentre         = "platform"
    }
  }
}
