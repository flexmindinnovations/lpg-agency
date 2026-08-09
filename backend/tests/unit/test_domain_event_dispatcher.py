"""`DomainEventDispatcher` — no database required."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from lpg.domain.common.base import DomainEvent
from lpg.infrastructure.events.dispatcher import DomainEventDispatcher


@dataclass(frozen=True, slots=True)
class _EventA(DomainEvent):
    payload: str = ""


@dataclass(frozen=True, slots=True)
class _EventB(DomainEvent):
    payload: str = ""


class TestRegisterAndDispatch:
    async def test_invokes_the_registered_handler(self) -> None:
        dispatcher = DomainEventDispatcher()
        received: list[DomainEvent] = []

        async def handler(event: DomainEvent) -> None:
            received.append(event)

        dispatcher.register(_EventA, handler)
        event = _EventA(payload="hello")

        await dispatcher.dispatch([event])

        assert received == [event]

    async def test_does_not_invoke_a_handler_registered_for_a_different_event_type(self) -> None:
        dispatcher = DomainEventDispatcher()
        received: list[DomainEvent] = []

        async def handler(event: DomainEvent) -> None:
            received.append(event)

        dispatcher.register(_EventB, handler)

        await dispatcher.dispatch([_EventA(payload="ignored")])

        assert received == []

    async def test_invokes_multiple_handlers_for_the_same_event_type_in_registration_order(
        self,
    ) -> None:
        dispatcher = DomainEventDispatcher()
        order: list[str] = []

        async def first(_event: DomainEvent) -> None:
            order.append("first")

        async def second(_event: DomainEvent) -> None:
            order.append("second")

        dispatcher.register(_EventA, first)
        dispatcher.register(_EventA, second)

        await dispatcher.dispatch([_EventA()])

        assert order == ["first", "second"]

    async def test_dispatches_multiple_events_in_order(self) -> None:
        dispatcher = DomainEventDispatcher()
        received: list[str] = []

        async def handler(event: DomainEvent) -> None:
            assert isinstance(event, _EventA)
            received.append(event.payload)

        dispatcher.register(_EventA, handler)

        await dispatcher.dispatch([_EventA(payload="one"), _EventA(payload="two")])

        assert received == ["one", "two"]

    async def test_no_registered_handler_is_a_silent_no_op(self) -> None:
        dispatcher = DomainEventDispatcher()

        await dispatcher.dispatch([_EventA()])  # must not raise

    async def test_empty_event_list_is_a_no_op(self) -> None:
        dispatcher = DomainEventDispatcher()
        calls = 0

        async def handler(_event: DomainEvent) -> None:
            nonlocal calls
            calls += 1

        dispatcher.register(_EventA, handler)

        await dispatcher.dispatch([])

        assert calls == 0

    async def test_handler_exception_propagates(self) -> None:
        dispatcher = DomainEventDispatcher()

        async def failing_handler(_event: DomainEvent) -> None:
            msg = "handler failure"
            raise RuntimeError(msg)

        dispatcher.register(_EventA, failing_handler)

        with pytest.raises(RuntimeError, match="handler failure"):
            await dispatcher.dispatch([_EventA()])

    async def test_a_failing_handler_does_not_prevent_earlier_handlers_from_having_run(
        self,
    ) -> None:
        dispatcher = DomainEventDispatcher()
        ran: list[str] = []

        async def first(_event: DomainEvent) -> None:
            ran.append("first")

        async def failing(_event: DomainEvent) -> None:
            ran.append("failing")
            msg = "boom"
            raise RuntimeError(msg)

        dispatcher.register(_EventA, first)
        dispatcher.register(_EventA, failing)

        with pytest.raises(RuntimeError):
            await dispatcher.dispatch([_EventA()])

        assert ran == ["first", "failing"]
