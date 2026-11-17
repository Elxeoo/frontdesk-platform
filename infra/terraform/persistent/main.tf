module "network" {
  source = "../modules/network"

  vnet_name           = "vnet-frontdesk-dev"
  resource_group_name = "rg-frontdesk-dev"
  location            = "austriaeast"

  vnet_address_space                       = ["10.1.0.0/16"]
  aks_subnet_address_prefixes              = ["10.1.0.0/24"]
  private_endpoint_subnet_address_prefixes = ["10.1.1.0/27"]
}
