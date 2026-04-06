"""FastAPI router for the Google Home Cloud-to-Cloud fulfillment endpoint."""
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from google_home.handlers import handle_fulfillment
from google_home.models import GoogleRequest

router = APIRouter(prefix="/google", tags=["google-home"])
logger = logging.getLogger(__name__)


@router.post("/fulfillment")
async def google_fulfillment(request: Request):
    """Receive and dispatch Google Home fulfillment intents.

    Google sends SYNC, QUERY, and EXECUTE intents to this endpoint.

    Configure this URL in the Google Home Developer Console under:
      Cloud-to-Cloud → Actions → Fulfillment URL
    """
    # Extract bearer token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    bearer_token = auth_header.removeprefix("Bearer ").strip()

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.debug("Google Home intent received: %s", body)

    try:
        google_request = GoogleRequest.model_validate(body)
    except Exception as exc:
        logger.error("Failed to parse Google fulfillment request: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid request body")

    response = await handle_fulfillment(google_request, bearer_token)
    return JSONResponse(content=response)
