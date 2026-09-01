from enum import StrEnum


class ComplaintCategory(StrEnum):
    SHORT_DELIVERY = "ShortDelivery"
    DAMAGED_CYLINDER = "DamagedCylinder"
    BILLING_DISPUTE = "BillingDispute"
    DRIVER_CONDUCT = "DriverConduct"
    LATE_DELIVERY = "LateDelivery"
    OTHER = "Other"


class ComplaintPriority(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ComplaintStatus(StrEnum):
    OPEN = "Open"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "InProgress"
    RESOLVED = "Resolved"
    REJECTED = "Rejected"
    CLOSED = "Closed"


class ResolutionOutcome(StrEnum):
    RESOLVED = "Resolved"
    COMPENSATED = "Compensated"
    REJECTED = "Rejected"
