"""API router for driver cash handovers (R10, `CashShortfallDeclared`)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from lpg.api.v1.dependencies.accounting import (
    get_cash_handover_number_sequence,
    get_cash_handover_repository,
)
from lpg.api.v1.dependencies.delivery import get_driver_repository, get_route_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_idempotency_service
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.cash_handover import (
    CashBookCollectionResponse,
    CashBookResponse,
    CashHandoverRegisterEntryResponse,
    CashHandoverResponse,
    CashHandoverReviewResponse,
    CashInHandResponse,
    DeclareCashHandoverRequest,
    DriverCashInHandResponse,
    ReviewCashHandoverRequest,
    RouteCashHandoverResponse,
)
from lpg.application.accounting.ports import CashHandoverNumberSequence, CashHandoverRepository
from lpg.application.accounting.use_cases import (
    DeclareCashHandoverCommand,
    DeclareCashHandoverUseCase,
    GetCashBookQuery,
    GetCashBookUseCase,
    GetRouteCashHandoverViewQuery,
    GetRouteCashHandoverViewUseCase,
    ListCashHandoverRegisterQuery,
    ListCashHandoverRegisterUseCase,
    ListCashInHandQuery,
    ListCashInHandUseCase,
    ReviewCashHandoverCommand,
    ReviewCashHandoverUseCase,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.delivery.ports import DriverRepository, RouteRepository
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.infrastructure.idempotency.service import IdempotencyService, run_idempotent

if TYPE_CHECKING:
    from lpg.application.accounting.ports import CashHandoverRegisterEntry, DriverCashInHand
    from lpg.domain.accounting.cash_handover import CashHandover

router = APIRouter(prefix="/cash-handovers", tags=["Cash Handovers"])

_IST = ZoneInfo("Asia/Kolkata")


def _to_response(handover: CashHandover) -> CashHandoverResponse:
    return CashHandoverResponse.model_validate(handover)


def _in_hand_response(rows: list[DriverCashInHand]) -> CashInHandResponse:
    return CashInHandResponse(
        total_cash=sum((r.cash_amount for r in rows), Decimal("0")),
        drivers=[
            DriverCashInHandResponse(
                driver_id=r.driver_id,
                driver_name=r.driver_name,
                route_count=r.route_count,
                stop_count=r.stop_count,
                cash_amount=r.cash_amount,
                upi_amount=r.upi_amount,
                oldest_route_date=r.oldest_route_date,
            )
            for r in rows
        ],
    )


@router.get(
    "/cash-in-hand/mine",
    response_model=CashInHandResponse,
    dependencies=[Depends(require_permission("cash_handovers:declare"))],
    summary="Cash the signed-in driver is carrying",
)
async def get_my_cash_in_hand(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
) -> CashInHandResponse:
    driver = (
        await driver_repository.get_by_identity_user_id(principal.user_id)
        if principal.user_id is not None
        else None
    )
    if driver is None:
        return CashInHandResponse(total_cash=Decimal("0"), drivers=[])
    rows = await ListCashInHandUseCase(cash_handover_repository).execute(
        ListCashInHandQuery(driver_id=driver.id)
    )
    return _in_hand_response(rows)


@router.get(
    "/cash-in-hand",
    response_model=CashInHandResponse,
    dependencies=[Depends(require_permission("cash_handovers:review"))],
    summary="Cash each driver is carrying (collected, not yet handed over)",
)
async def list_cash_in_hand(
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    driver_id: uuid.UUID | None = None,
) -> CashInHandResponse:
    rows = await ListCashInHandUseCase(cash_handover_repository).execute(
        ListCashInHandQuery(driver_id=driver_id)
    )
    return _in_hand_response(rows)


@router.get(
    "/cash-book",
    response_model=CashBookResponse,
    dependencies=[Depends(require_permission("cash_handovers:review"))],
    summary="Daily cash book: collected by mode, handed over, reviewed",
)
async def get_cash_book(
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    day: Annotated[date | None, Query(alias="date", description="IST day; default today")] = None,
) -> CashBookResponse:
    book_day = day or datetime.now(_IST).date()
    start = datetime.combine(book_day, time.min, tzinfo=_IST)
    book = await GetCashBookUseCase(cash_handover_repository).execute(
        GetCashBookQuery(day_from=start, day_to=start + timedelta(days=1))
    )
    in_hand = await ListCashInHandUseCase(cash_handover_repository).execute(ListCashInHandQuery())
    return CashBookResponse(
        date=book_day,
        collections=[
            CashBookCollectionResponse(
                method=c.method, payment_count=c.payment_count, amount=c.amount
            )
            for c in book.collections
        ],
        total_collected=sum((c.amount for c in book.collections), Decimal("0")),
        handover_count=book.handover_count,
        expected_total=book.expected_total,
        handed_over_total=book.handed_over_total,
        shortfall_total=book.shortfall_total,
        excess_total=book.excess_total,
        accepted_total=book.accepted_total,
        disputed_total=book.disputed_total,
        pending_total=book.pending_total,
        pending_count=book.pending_count,
        cash_in_hand_total=sum((r.cash_amount for r in in_hand), Decimal("0")),
    )


@router.get(
    "/for-route/{route_id}",
    response_model=RouteCashHandoverResponse,
    dependencies=[Depends(require_permission("cash_handovers:declare"))],
)
async def get_route_cash_handover(
    route_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
) -> RouteCashHandoverResponse:
    """The Driver App's cash-handover screen: `expected_amount` (from the
    route's real cash proof-of-delivery records) plus the declared handover
    once it exists.

    A `driver` principal sees only their own routes; dispatch staff (who also
    hold `cash_handovers:declare`, per `c039189dfbdc`) can read any route in
    their tenant — same "or dispatcher/manager on their behalf" split as the
    declare endpoint. Either way `route_repository.get_by_id`'s RLS keeps it
    tenant-scoped, and a route the caller can't see is a `404`.
    """
    driver = (
        await driver_repository.get_by_identity_user_id(principal.user_id)
        if principal.user_id is not None
        else None
    )

    use_case = GetRouteCashHandoverViewUseCase(cash_handover_repository, route_repository)
    view = await use_case.execute(
        GetRouteCashHandoverViewQuery(
            route_id=route_id,
            driver_id=driver.id if driver is not None else None,
        )
    )
    return RouteCashHandoverResponse.model_validate(view)


@router.post(
    "",
    response_model=CashHandoverResponse,
    status_code=201,
    dependencies=[Depends(require_permission("cash_handovers:declare"))],
)
async def declare_cash_handover(
    http_request: Request,
    request: DeclareCashHandoverRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    handover_number_sequence: Annotated[
        CashHandoverNumberSequence, Depends(get_cash_handover_number_sequence)
    ],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> CashHandoverResponse:
    """A driver (or dispatcher/manager on their behalf) declares the cash
    handed over at the end of a route. `expected_amount` is computed
    server-side from real cash-payment proof-of-delivery records — never
    trusted from the request.

    `Idempotency-Key` is optional (the offline Driver App sends one so a
    queued retry replays rather than hitting the `uq_cash_handover_route`
    409) — see `run_idempotent`.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    declared_by = principal.user_id
    use_case = DeclareCashHandoverUseCase(
        cash_handover_repository, route_repository, unit_of_work, handover_number_sequence
    )

    async def _operation() -> dict[str, Any]:
        handover = await use_case.execute(
            DeclareCashHandoverCommand(
                driver_id=request.driver_id,
                route_id=request.route_id,
                actual_amount=request.actual_amount,
                declared_by=declared_by,
                denominations=request.denominations,
                variance_reason=request.variance_reason,
            )
        )
        return _to_response(handover).model_dump(mode="json")

    result = await run_idempotent(
        idempotency_service,
        tenant_id=principal.tenant_id,
        idempotency_key=http_request.headers.get("Idempotency-Key"),
        fingerprint_payload=request.model_dump(mode="json"),
        operation=_operation,
    )
    return CashHandoverResponse.model_validate(result)


def _register_entry_to_response(
    entry: CashHandoverRegisterEntry,
) -> CashHandoverRegisterEntryResponse:
    handover = entry.handover
    review = entry.review
    excess = handover.actual_amount - handover.expected_amount
    return CashHandoverRegisterEntryResponse(
        id=handover.id,
        handover_number=handover.handover_number,
        driver_id=handover.driver_id,
        driver_name=entry.driver_name,
        route_id=handover.route_id,
        route_date=entry.route_date,
        vehicle_registration=entry.vehicle_registration,
        cash_stop_count=entry.cash_stop_count,
        expected_amount=handover.expected_amount,
        actual_amount=handover.actual_amount,
        shortfall=handover.shortfall,
        excess=excess if excess > 0 else Decimal("0"),
        declared_at=handover.declared_at,
        denominations=handover.denominations,
        variance_reason=handover.variance_reason,
        upi_expected=handover.upi_expected,
        review_status=review.outcome if review is not None else "pending",
        review=(
            CashHandoverReviewResponse(
                id=review.id,
                outcome=review.outcome,
                note=review.note,
                reviewed_by=review.reviewed_by,
                reviewed_by_name=entry.reviewer_name,
                reviewed_at=review.reviewed_at,
            )
            if review is not None
            else None
        ),
    )


@router.get(
    "",
    response_model=list[CashHandoverRegisterEntryResponse],
    dependencies=[Depends(require_permission("cash_handovers:review"))],
)
async def list_cash_handover_register(
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    declared_from: Annotated[date | None, Query(description="First day, inclusive (IST)")] = None,
    declared_to: Annotated[date | None, Query(description="Last day, inclusive (IST)")] = None,
    driver_id: uuid.UUID | None = None,
    review_status: Annotated[str | None, Query(description="pending, accepted or disputed")] = None,
) -> list[CashHandoverRegisterEntryResponse]:
    """The accountant's cash-handover register (DA-33): every driver's
    declared cash against what their deliveries say they collected, with
    shortfalls and the office's review.
    """
    entries = await ListCashHandoverRegisterUseCase(cash_handover_repository).execute(
        ListCashHandoverRegisterQuery(
            declared_from=(
                datetime.combine(declared_from, time.min, tzinfo=_IST) if declared_from else None
            ),
            declared_to=(
                datetime.combine(declared_to + timedelta(days=1), time.min, tzinfo=_IST)
                if declared_to
                else None
            ),
            driver_id=driver_id,
            review_status=review_status,
        )
    )
    return [_register_entry_to_response(entry) for entry in entries]


@router.post(
    "/{cash_handover_id}/review",
    response_model=CashHandoverReviewResponse,
    status_code=201,
    dependencies=[Depends(require_permission("cash_handovers:review"))],
)
async def review_cash_handover(
    cash_handover_id: uuid.UUID,
    request: ReviewCashHandoverRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CashHandoverReviewResponse:
    """Accept the counted cash, or dispute it with a note. One review per
    handover; the person who declared it cannot review it. A short handover
    can only be accepted with a note on how the shortfall was settled.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    review = await ReviewCashHandoverUseCase(cash_handover_repository, unit_of_work).execute(
        ReviewCashHandoverCommand(
            cash_handover_id=cash_handover_id,
            outcome=request.outcome,
            note=request.note,
            reviewed_by=principal.user_id,
        )
    )
    return CashHandoverReviewResponse(
        id=review.id,
        outcome=review.outcome,
        note=review.note,
        reviewed_by=review.reviewed_by,
        reviewed_at=review.reviewed_at,
    )
