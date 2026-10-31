variable "team_b_hostname" {
  type    = string
  default = "b.lab.test"
}

module "team_a" {
  source   = "./modules/service_contract"
  team     = "team-a"
  hostname = "a.lab.test"
}

module "team_b" {
  source   = "./modules/service_contract"
  team     = "team-b"
  hostname = var.team_b_hostname
}

output "contracts" {
  value = {
    team_a = module.team_a.contract
    team_b = module.team_b.contract
  }
}
