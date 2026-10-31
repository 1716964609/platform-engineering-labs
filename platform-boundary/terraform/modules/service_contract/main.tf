variable "team" {
  type = string
}

variable "hostname" {
  type = string

  validation {
    condition     = endswith(var.hostname, ".lab.test")
    error_message = "hostname must end with .lab.test"
  }
}

resource "terraform_data" "contract" {
  input = {
    team     = var.team
    hostname = var.hostname

    gateway_owner = "platform-team"
    route_owner   = var.team
  }
}

output "contract" {
  value = terraform_data.contract.output
}
