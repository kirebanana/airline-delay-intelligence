terraform {
  required_version = ">= 1.13.4, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.33.0"
    }
  }
  backend "s3" {
    bucket              = "airline-state-336805808138-us-east-2"
    key                 = "aws/ingestion.tfstate"
    region              = "us-east-2"
    profile             = "airline-old-dev"
    allowed_account_ids = ["336805808138"]
    encrypt             = true
    use_lockfile        = true
  }
}

provider "aws" {
  region              = "us-east-2"
  profile             = "airline-old-dev"
  allowed_account_ids = ["336805808138"]
  default_tags {
    tags = {
      Project   = "airline-delay-intelligence"
      ManagedBy = "terraform"
      Scope     = "ingestion-01-04"
    }
  }
}
