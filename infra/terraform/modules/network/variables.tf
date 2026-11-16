variable "vnet_name" {
  description = "Name of the virtual network."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the network resources."
  type        = string
}

variable "location" {
  description = "Azure region for all network resources."
  type        = string
}

variable "vnet_address_space" {
  description = "Address space of the virtual network, in CIDR notation."
  type        = list(string)
}

variable "aks_subnet_address_prefixes" {
  description = "Address prefixes of the AKS node subnet, in CIDR notation."
  type        = list(string)
}

variable "private_endpoint_subnet_address_prefixes" {
  description = "Address prefixes of the private endpoint subnet, in CIDR notation."
  type        = list(string)
}
