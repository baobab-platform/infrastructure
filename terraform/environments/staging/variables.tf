variable "aws_region" {
  description = "AWS region for the staging environment."
  type        = string
  default     = "af-south-1"

  validation {
    condition     = var.aws_region == "af-south-1"
    error_message = "ADR-Infra-0002 fixes the initial staging region to af-south-1."
  }
}

variable "environment" {
  description = "Environment identity. This composition is staging-only."
  type        = string
  default     = "staging"

  validation {
    condition     = var.environment == "staging"
    error_message = "This root module may only manage the staging environment."
  }
}

variable "vpc_cidr" {
  description = "CIDR for the isolated staging VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "availability_zones" {
  description = "Two af-south-1 availability zones used by the production-shaped staging slice."
  type        = list(string)
  default     = ["af-south-1a", "af-south-1b"]

  validation {
    condition     = length(var.availability_zones) == 2 && alltrue([for az in var.availability_zones : startswith(az, "af-south-1")])
    error_message = "Exactly two af-south-1 availability zones are required."
  }
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Ingress subnet CIDRs, one per availability zone."
  default     = ["10.40.0.0/24", "10.40.1.0/24"]
}

variable "application_subnet_cidrs" {
  type        = list(string)
  description = "Private application subnet CIDRs, one per availability zone."
  default     = ["10.40.10.0/24", "10.40.11.0/24"]
}

variable "data_subnet_cidrs" {
  type        = list(string)
  description = "Private data subnet CIDRs, one per availability zone."
  default     = ["10.40.20.0/24", "10.40.21.0/24"]
}

variable "management_subnet_cidrs" {
  type        = list(string)
  description = "Private management subnet CIDRs, one per availability zone."
  default     = ["10.40.30.0/24", "10.40.31.0/24"]
}

variable "public_ingress_cidrs" {
  type        = list(string)
  description = "CIDRs permitted to reach the public HTTPS ALB. Staging defaults to Internet-reachable browser federation."
  default     = ["0.0.0.0/0"]
}

variable "cloud_map_namespace" {
  type        = string
  description = "Private DNS namespace for staging service discovery."
  default     = "staging.baobab.internal"
}
