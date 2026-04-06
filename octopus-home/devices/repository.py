"""Database CRUD for devices and automation rules."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from devices.models import AutomationRule, Device


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, name: str, description: str, device_type: str, user_id: str) -> Device:
        now = datetime.now(timezone.utc)
        device = Device(
            name=name,
            description=description,
            device_type=device_type,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        self._session.add(device)
        await self._session.commit()
        await self._session.refresh(device)
        return device

    async def get(self, device_id: str, user_id: str) -> Device | None:
        result = await self._session.execute(
            select(Device).where(Device.id == device_id, Device.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, user_id: str) -> list[Device]:
        result = await self._session.execute(
            select(Device).where(Device.user_id == user_id).order_by(Device.created_at)
        )
        return list(result.scalars().all())

    async def update_state(self, device_id: str, state: bool) -> Device | None:
        result = await self._session.execute(select(Device).where(Device.id == device_id))
        device = result.scalar_one_or_none()
        if device:
            device.state = state
            device.updated_at = datetime.now(timezone.utc)
            await self._session.commit()
            await self._session.refresh(device)
        return device

    async def delete(self, device_id: str, user_id: str) -> bool:
        device = await self.get(device_id, user_id)
        if device:
            await self._session.delete(device)
            await self._session.commit()
            return True
        return False


class AutomationRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        device_id: str,
        price_threshold_pence: float,
        action_below_threshold: str,
        user_id: str,
    ) -> AutomationRule:
        rule = AutomationRule(
            device_id=device_id,
            price_threshold_pence=price_threshold_pence,
            action_below_threshold=action_below_threshold,
            user_id=user_id,
        )
        self._session.add(rule)
        await self._session.commit()
        await self._session.refresh(rule)
        return rule

    async def list_enabled(self) -> list[AutomationRule]:
        result = await self._session.execute(
            select(AutomationRule).where(AutomationRule.enabled == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def list_for_user(self, user_id: str) -> list[AutomationRule]:
        result = await self._session.execute(
            select(AutomationRule).where(AutomationRule.user_id == user_id)
        )
        return list(result.scalars().all())

    async def delete(self, rule_id: int, user_id: str) -> bool:
        result = await self._session.execute(
            select(AutomationRule).where(
                AutomationRule.id == rule_id, AutomationRule.user_id == user_id
            )
        )
        rule = result.scalar_one_or_none()
        if rule:
            await self._session.delete(rule)
            await self._session.commit()
            return True
        return False
