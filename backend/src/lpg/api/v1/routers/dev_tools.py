"""Dev/E2E-only endpoints. Registered in `api/app.py` only when `not
settings.is_production`, so it isn't even present in the route table in a
real deployment.

Reads back OTP codes `LoggingOtpDelivery.send()` / `SmsOtpDelivery.send()`
stashed in Redis, so a local/E2E/UAT run can sign in and complete the
Deliver-order flow without the customer's handset or scraping stdout logs.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.identity import get_redis_client, require_permission
from lpg.api.v1.dependencies.order import get_order_repository
from lpg.application.customer.ports import CustomerRepository
from lpg.application.order.ports import OrderRepository
from lpg.infrastructure.identity.otp_delivery import dev_otp_inbox_key
from lpg.infrastructure.redis.client import RedisClient

router = APIRouter(prefix="/dev", tags=["Dev Tools"], include_in_schema=False)


@router.get("/otp-inbox/{phone_number}")
async def get_dev_otp(
    phone_number: str,
    redis: Annotated[RedisClient, Depends(get_redis_client)],
) -> dict[str, str]:
    code = await redis.client.get(dev_otp_inbox_key(phone_number))
    if code is None:
        raise HTTPException(status_code=404, detail="No OTP pending for this phone number.")
    return {"code": code}


@router.get(
    "/orders/{order_id}/delivery-otp",
    dependencies=[Depends(require_permission("orders:deliver"))],
)
async def get_dev_delivery_otp(
    order_id: uuid.UUID,
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    redis: Annotated[RedisClient, Depends(get_redis_client)],
) -> dict[str, str]:
    """The last delivery OTP sent for this order's customer — the Driver
    App's "Testing only" banner on Record delivery. Tenant-scoped through
    the authenticated repositories (RLS).
    """
    order = await order_repository.get_by_id(order_id)
    customer = await customer_repository.get_by_id(order.customer_id) if order is not None else None
    code = (
        await redis.client.get(dev_otp_inbox_key(customer.phone_number, "delivery"))
        if customer is not None
        else None
    )
    if code is None:
        raise HTTPException(status_code=404, detail="No delivery OTP pending for this order.")
    return {"code": code}
