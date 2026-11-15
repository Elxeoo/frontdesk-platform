resource "azurerm_resource_group" "tfstate" {
  name     = "rg-frontdesk-tfstate"
  location = "austriaeast"

  tags = {
    project = "frontdesk"
    layer   = "persistent"
  }
}

# Storage account names are global: lowercase, 3-24 chars.
resource "azurerm_storage_account" "tfstate" {
  name                     = "stfrontdesktfelxeoo"
  resource_group_name      = azurerm_resource_group.tfstate.name
  location                 = azurerm_resource_group.tfstate.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  # Entra ID only, no shared keys.
  shared_access_key_enabled       = false
  default_to_oauth_authentication = true
  allow_nested_items_to_be_public = false

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
  }

  tags = azurerm_resource_group.tfstate.tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_container" "tfstate" {
  name               = "tfstate"
  storage_account_id = azurerm_storage_account.tfstate.id
}
