---
name: Terraform Module Builder
description: Draft modular, reusable Infrastructure-as-Code Terraform modules for cloud infrastructure.
metadata:
  source: skills/terraform-module-builder/terraform-module-builder.md
---

# Terraform Module Builder

## Prerequisites & Dependencies
- Terraform CLI 1.5+ installed and configured
- Cloud provider credentials (AWS, GCP, Azure) via `~/.aws/credentials`, `gcloud`, or `az cli`
- Text editor or IDE with HCL syntax highlighting
- Optional: `tflint` and `terraform fmt` for linting and formatting

## Execution Steps
1. Define the module directory structure: `variables.tf`, `inputs.tf`, `outputs.tf`, `main.tf`, and an optional `README.md`
2. Write `variables.tf` with clear input variables: names, types, defaults, and validation rules (`validation` block)
3. Write `main.tf` with resource definitions that accept input variables and produce logical outputs
4. Write `outputs.tf` with descriptive output values that consumers can reference in other modules or scripts
5. Add a `README.md` explaining the module's purpose, inputs, outputs, usage examples, and versioning scheme
6. Test the module locally: `terraform init`, `terraform plan`, and `terraform apply` in a throwaway workspace
7. Version the module: create a `vX.Y.Z` git tag and push to a registry (Terraform Registry or private Git repo)

```hcl
# variables.tf
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

# main.tf
resource "aws_vpc" "example" {
  cidr_block = var.vpc_cidr
}

resource "aws_instance" "example" {
  instance_type = var.instance_type
  ami           = data.aws_ami.default.id
  vpc_id        = aws_vpc.example.id
}

# outputs.tf
output "vpc_id" {
  description = "ID of the created VPC"
  value       = aws_vpc.example.id
}
```

```bash
terraform init
terraform plan -var="vpc_cidr=10.1.0.0/16"
terraform apply -auto-approve
```
