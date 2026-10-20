from enum import StrEnum


class ComplaintCategory(StrEnum):
    SHORT_DELIVERY = "ShortDelivery"
    DAMAGED_CYLINDER = "DamagedCylinder"
    BILLING_DISPUTE = "BillingDispute"
    DRIVER_CONDUCT = "DriverConduct"
    LATE_DELIVERY = "LateDelivery"
    #: A suspected leak or other safety hazard — always Critical (DO-19).
    GAS_LEAK = "GasLeak"
    OTHER = "Other"


#: Categories that are safety issues: raised at Critical priority whatever
#: the caller picked, so they get the shortest SLA.
SAFETY_CATEGORIES = frozenset({ComplaintCategory.GAS_LEAK})


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
