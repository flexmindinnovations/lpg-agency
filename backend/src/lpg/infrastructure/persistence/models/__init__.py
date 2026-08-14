"""ORM models package initialization.

Import all ORM models here so that SQLAlchemy's `DeclarativeBase` registry
registers all tables and foreign key relationships at startup.
"""

from lpg.infrastructure.persistence.models.accounting import (
    InvoiceLineModel,
    InvoiceModel,
)
from lpg.infrastructure.persistence.models.audit_log import AuditLogModel
from lpg.infrastructure.persistence.models.customer import (
    CustomerAddressModel,
    CustomerModel,
    KycDocumentModel,
)
from lpg.infrastructure.persistence.models.cylinder_ledger import (
    CylinderBalanceModel,
    CylinderLedgerModel,
    LedgerTransactionModel,
)
from lpg.infrastructure.persistence.models.delivery import (
    DriverModel,
    RouteModel,
    RouteStopModel,
    VehicleModel,
)
from lpg.infrastructure.persistence.models.identity import (
    IdentityUserModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
)
from lpg.infrastructure.persistence.models.inventory import (
    GoodsReceiptNoteModel,
    InventoryBalanceModel,
    InventoryLocationModel,
    InventoryTransactionModel,
    ReconciliationRecordModel,
)
from lpg.infrastructure.persistence.models.order import (
    CancellationRecordModel,
    FailedDeliveryRecordModel,
    OrderLineModel,
    OrderModel,
    OrderStatusHistoryModel,
    ProofOfDeliveryModel,
)
from lpg.infrastructure.persistence.models.notification import (
    InAppNotificationModel,
    NotificationLogModel,
)
from lpg.infrastructure.persistence.models.tenant import (
    BranchModel,
    CylinderTypeModel,
    EmployeeModel,
    FeatureFlagOverrideModel,
    PriceListModel,
    TenantConfigurationModel,
    TenantModel,
    WarehouseModel,
)

__all__ = [
    "AuditLogModel",
    "BranchModel",
    "CancellationRecordModel",
    "CustomerAddressModel",
    "CustomerModel",
    "CylinderBalanceModel",
    "CylinderLedgerModel",
    "CylinderTypeModel",
    "DriverModel",
    "EmployeeModel",
    "FailedDeliveryRecordModel",
    "FeatureFlagOverrideModel",
    "GoodsReceiptNoteModel",
    "IdentityUserModel",
    "InAppNotificationModel",
    "InventoryBalanceModel",
    "InventoryLocationModel",
    "InventoryTransactionModel",
    "InvoiceLineModel",
    "InvoiceModel",
    "KycDocumentModel",
    "LedgerTransactionModel",
    "NotificationLogModel",
    "OrderLineModel",
    "OrderModel",
    "OrderStatusHistoryModel",
    "PasswordResetTokenModel",
    "PriceListModel",
    "ProofOfDeliveryModel",
    "ReconciliationRecordModel",
    "RefreshTokenModel",
    "RouteModel",
    "RouteStopModel",
    "TenantConfigurationModel",
    "TenantModel",
    "VehicleModel",
    "WarehouseModel",
]
