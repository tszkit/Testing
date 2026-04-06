"""Octopus Home Automation — FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth.router import router as auth_router
from alexa.router import router as alexa_router
from google_home.router import router as google_router
from core.config import settings
from core.database import create_tables, get_db
from core.scheduler import scheduler, setup_scheduler
from devices.models import AutomationRule
from devices.repository import AutomationRuleRepository, DeviceRepository
from octopus.service import fetch_and_store_prices, get_current_price, get_cheapest_slots, get_upcoming_prices

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Octopus Home Automation...")
    await create_tables()
    setup_scheduler()
    scheduler.start()
    # Fetch prices immediately on startup
    await fetch_and_store_prices()
    logger.info("Ready.")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Octopus Home Automation",
    description=(
        "Controls electrical appliances based on Octopus Agile half-hourly electricity prices. "
        "Integrates with Amazon Alexa Smart Home and Google Home."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(alexa_router)
app.include_router(google_router)


# ---------------------------------------------------------------------------
# Octopus pricing endpoints
# ---------------------------------------------------------------------------

prices_router = APIRouter(prefix="/prices", tags=["prices"])


@prices_router.get("/current")
async def current_price():
    """Return the current Octopus Agile price in pence/kWh."""
    price = await get_current_price()
    if price is None:
        raise HTTPException(status_code=503, detail="Price data unavailable — fetch may be pending")
    return {"price_pence_per_kwh": price, "threshold_pence": settings.price_cheap_threshold_pence, "is_cheap": price <= settings.price_cheap_threshold_pence}


@prices_router.get("/upcoming")
async def upcoming_prices(hours: int = 24):
    """Return upcoming price slots for the next N hours (default 24)."""
    slots = await get_upcoming_prices(hours_ahead=hours)
    return [
        {
            "valid_from": s.valid_from.isoformat(),
            "valid_to": s.valid_to.isoformat(),
            "price_pence_per_kwh": s.value_inc_vat,
        }
        for s in slots
    ]


@prices_router.get("/cheapest")
async def cheapest_slots(n: int = 3, hours: int = 24):
    """Return the N cheapest half-hour slots in the next H hours."""
    slots = await get_cheapest_slots(n=n, hours_ahead=hours)
    return [
        {
            "valid_from": s.valid_from.isoformat(),
            "valid_to": s.valid_to.isoformat(),
            "price_pence_per_kwh": s.value_inc_vat,
        }
        for s in slots
    ]


app.include_router(prices_router)


# ---------------------------------------------------------------------------
# Device management endpoints
# ---------------------------------------------------------------------------

devices_router = APIRouter(prefix="/devices", tags=["devices"])

# Demo user — replace with real auth middleware in production
DEMO_USER = "homeuser1"


class DeviceCreate(BaseModel):
    name: str
    description: str = ""
    device_type: str = "switch"


class DeviceStateUpdate(BaseModel):
    state: bool


@devices_router.get("")
async def list_devices(db: AsyncSession = Depends(get_db)):
    repo = DeviceRepository(db)
    devices = await repo.list_all(DEMO_USER)
    return [
        {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "device_type": d.device_type,
            "state": d.state,
            "created_at": d.created_at.isoformat(),
        }
        for d in devices
    ]


@devices_router.post("", status_code=201)
async def create_device(body: DeviceCreate, db: AsyncSession = Depends(get_db)):
    repo = DeviceRepository(db)
    device = await repo.create(
        name=body.name,
        description=body.description,
        device_type=body.device_type,
        user_id=DEMO_USER,
    )
    return {"id": device.id, "name": device.name, "state": device.state}


@devices_router.get("/{device_id}")
async def get_device(device_id: str, db: AsyncSession = Depends(get_db)):
    repo = DeviceRepository(db)
    device = await repo.get(device_id, DEMO_USER)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {
        "id": device.id,
        "name": device.name,
        "description": device.description,
        "device_type": device.device_type,
        "state": device.state,
        "updated_at": device.updated_at.isoformat(),
    }


@devices_router.patch("/{device_id}/state")
async def update_device_state(device_id: str, body: DeviceStateUpdate):
    from devices.service import set_device_state
    device = await set_device_state(device_id, body.state)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"id": device.id, "name": device.name, "state": device.state}


@devices_router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: str, db: AsyncSession = Depends(get_db)):
    repo = DeviceRepository(db)
    deleted = await repo.delete(device_id, DEMO_USER)
    if not deleted:
        raise HTTPException(status_code=404, detail="Device not found")


app.include_router(devices_router)


# ---------------------------------------------------------------------------
# Automation rule endpoints
# ---------------------------------------------------------------------------

rules_router = APIRouter(prefix="/rules", tags=["automation"])


class RuleCreate(BaseModel):
    device_id: str
    price_threshold_pence: float
    action_below_threshold: str = "on"


@rules_router.get("")
async def list_rules(db: AsyncSession = Depends(get_db)):
    repo = AutomationRuleRepository(db)
    rules = await repo.list_for_user(DEMO_USER)
    return [
        {
            "id": r.id,
            "device_id": r.device_id,
            "price_threshold_pence": r.price_threshold_pence,
            "action_below_threshold": r.action_below_threshold,
            "enabled": r.enabled,
        }
        for r in rules
    ]


@rules_router.post("", status_code=201)
async def create_rule(body: RuleCreate, db: AsyncSession = Depends(get_db)):
    # Verify device exists
    device_repo = DeviceRepository(db)
    device = await device_repo.get(body.device_id, DEMO_USER)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    repo = AutomationRuleRepository(db)
    rule = await repo.create(
        device_id=body.device_id,
        price_threshold_pence=body.price_threshold_pence,
        action_below_threshold=body.action_below_threshold,
        user_id=DEMO_USER,
    )
    return {"id": rule.id, "device_id": rule.device_id, "price_threshold_pence": rule.price_threshold_pence}


@rules_router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    repo = AutomationRuleRepository(db)
    deleted = await repo.delete(rule_id, DEMO_USER)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")


app.include_router(rules_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
