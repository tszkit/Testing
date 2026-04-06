import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(256), default="")
    # Type: "switch" | "outlet"
    device_type: Mapped[str] = mapped_column(String(32), default="switch")
    state: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    automation_rules: Mapped[list["AutomationRule"]] = relationship(
        "AutomationRule", back_populates="device", cascade="all, delete-orphan"
    )


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), nullable=False)
    # Turn device on when price <= threshold, off when price > threshold
    price_threshold_pence: Mapped[float] = mapped_column(Float, nullable=False)
    # "on" = turn on below threshold; "off" = turn off below threshold
    action_below_threshold: Mapped[str] = mapped_column(String(8), default="on")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    device: Mapped["Device"] = relationship("Device", back_populates="automation_rules")
