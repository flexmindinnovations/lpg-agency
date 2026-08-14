from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RegisterEmployeeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: str = Field(..., description="Branch UUID")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: str = Field(..., min_length=1, max_length=20)
    role: str = Field(..., description="Role of the employee")
    email: str | None = Field(None, max_length=255)


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    branch_id: str
    employee_code: str
    first_name: str
    last_name: str
    phone_number: str
    role: str
    status: str
    email: str | None = None


class EmployeePageResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int
