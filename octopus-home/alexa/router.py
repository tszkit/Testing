"""FastAPI router for the Alexa Smart Home Skill endpoint."""
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from alexa.handlers import handle_directive
from alexa.models import AlexaRequest

router = APIRouter(prefix="/alexa", tags=["alexa"])
logger = logging.getLogger(__name__)


@router.post("/skill")
async def alexa_skill_endpoint(request: Request):
    """Receive and dispatch Alexa Smart Home Skill directives.

    Alexa sends all directives (Discovery, PowerController, ReportState, etc.)
    to this single endpoint over HTTPS POST.

    Configure this URL in the Alexa Developer Console under:
      Build → Smart Home → Default endpoint → HTTPS
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.debug("Alexa directive received: %s", body)

    try:
        alexa_request = AlexaRequest.model_validate(body)
    except Exception as exc:
        logger.error("Failed to parse Alexa directive: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Alexa directive")

    response = await handle_directive(alexa_request)
    return JSONResponse(content=response)
