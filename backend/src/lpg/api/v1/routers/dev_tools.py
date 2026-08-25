"""Dev/E2E-only endpoints. Registered in `api/app.py` only when `not
settings.is_production`, so it isn't even present in the route table in a
real deployment.

Right now this is a single endpoint: reading back the delivery OTP
`LoggingOtpDelivery.send()` stashed in Redis, so a local/E2E test can
complete the Deliver-order flow without scraping stdout logs for the code.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.identity import get_redis_client
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
