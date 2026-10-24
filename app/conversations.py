"""Conversation Room HTTP boundary; all sends require explicit Staff role."""
from uuid import UUID

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from app.activity import require_demo_staff
from app.xinjie_store import Store
from backend.conversation import ConversationService

router = APIRouter(prefix="/api/enquiries", tags=["conversations"])


@router.get("/{enquiry_id}/conversation")
def conversation(enquiry_id: UUID, request: Request):
    return ConversationService(Store(request.app.state.engine)).list(str(enquiry_id))


@router.post("/{enquiry_id}/messages")
def send_message(enquiry_id: UUID, request: Request, patch: dict = Body(...)):
    actor = require_demo_staff(request)
    result = ConversationService(Store(request.app.state.engine), request.app.state.telegram_sender).send(
        str(enquiry_id), patch, actor)
    return JSONResponse(result, status_code={"sent": 200, "failed": 502, "unknown": 202, "pending": 202}[result["status"]])
