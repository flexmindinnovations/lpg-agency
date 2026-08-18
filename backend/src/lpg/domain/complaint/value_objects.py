from enum import Enum


class ComplaintCategory(str, Enum):
    SHORT_DELIVERY = "ShortDelivery"
    DAMAGED_CYLINDER = "DamagedCylinder"
    BILLING_DISPUTE = "BillingDispute"
    DRIVER_CONDUCT = "DriverConduct"
    LATE_DELIVERY = "LateDelivery"
    OTHER = "Other"


class ComplaintPriority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class ComplaintStatus(str, Enum):
    OPEN = "Open"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "InProgress"
    RESOLVED = "Resolved"
    REJECTED = "Rejected"
    CLOSED = "Closed"


class ResolutionOutcome(str, Enum):
    RESOLVED = "Resolved"
    COMPENSATED = "Compensated"
    REJECTED = "Rejected"
