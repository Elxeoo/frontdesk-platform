terraform {
  backend "azurerm" {
    use_cli              = true
    use_azuread_auth     = true
    storage_account_name = "stfrontdesktfelxeoo"
    container_name       = "tfstate"
    key                  = "persistent.tfstate"
  }
}
