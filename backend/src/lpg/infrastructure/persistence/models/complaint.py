import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lpg.infrastructure.persistence.database import Base


class ComplaintModel(Base):
    __tablename__ = "complaint"
    __table_args__ = {"schema": "complaint"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.tenant.id"), nullable=False)
    complaint_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sla_due_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    assignments: Mapped[list["ComplaintAssignmentModel"]] = relationship(
        "ComplaintAssignmentModel", back_populates="complaint", cascade="all, delete-orphan"
    )
    resolution: Mapped["ComplaintResolutionModel | None"] = relationship(
        "ComplaintResolutionModel",
        back_populates="complaint",
        cascade="all, delete-orphan",
        uselist=False,
    )


class ComplaintAssignmentModel(Base):
    __tablename__ = "complaint_assignment"
    __table_args__ = {"schema": "complaint"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaint.complaint.id", ondelete="CASCADE"), nullable=False
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    complaint: Mapped["ComplaintModel"] = relationship(
        "ComplaintModel", back_populates="assignments"
    )


class ComplaintResolutionModel(Base):
    __tablename__ = "complaint_resolution"
    __table_args__ = {"schema": "complaint"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    complaint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complaint.complaint.id", ondelete="CASCADE"), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    resolution_notes: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_by: Mapped[uuid.UUID] = mapped_column(nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    complaint: Mapped["ComplaintModel"] = relationship(
        "ComplaintModel", back_populates="resolution"
    )
