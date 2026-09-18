"""Read-only access to canonical contracts owned by alos-contracts."""

from genesis.contracts.catalog import CanonicalContractCatalog, ContractValidationError

__all__ = ["CanonicalContractCatalog", "ContractValidationError"]
