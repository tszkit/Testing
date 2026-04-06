from datetime import datetime

from sqlalchemy import DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PriceSlot(Base):
    __tablename__ = "price_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    valid_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Price in pence per kWh including VAT
    value_inc_vat: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
