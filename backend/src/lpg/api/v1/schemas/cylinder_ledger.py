from pydantic import BaseModel, Field
import uuid

class AdjustLedgerBalanceRequest(BaseModel):
    cylinder_type_id: uuid.UUID = Field(..., description="The ID of the cylinder type.")
    delta: int = Field(..., description="The positive or negative amount to adjust the balance by.")
    reason: str = Field(..., description="The reason for this manual adjustment.")

class CylinderLedgerBalanceItem(BaseModel):
    cylinder_type_id: uuid.UUID
    quantity: int

class CylinderLedgerResponse(BaseModel):
    customer_id: uuid.UUID
    balances: list[CylinderLedgerBalanceItem]
