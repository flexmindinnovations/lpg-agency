from enum import StrEnum


class ComplaintCategory(StrEnum):
    SHORT_DELIVERY = "ShortDelivery"
    DAMAGED_CYLINDER = "DamagedCylinder"
    BILLING_DISPUTE = "BillingDispute"
    DRIVER_CONDUCT = "DriverConduct"
    LATE_DELIVERY = "LateDelivery"
    #: Gas leak, smell of gas, a hissing valve, a fire risk. Always raised at
    #: Critical priority (the shortest SLA) whatever the customer chose.
    GAS_LEAK_SAFETY = "GasLeakSafety"
    OTHER = "Other"


#: Categories that are safety issues: raised at Critical priority whatever
#: the caller picked, so they get the shortest SLA.
SAFETY_CATEGORIES = frozenset({ComplaintCategory.GAS_LEAK_SAFETY})


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
