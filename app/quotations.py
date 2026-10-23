"""Quotation routes sharing the Telegram application's database engine."""
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response
from uuid import UUID
from app.enquiries import get_enquiry

router = APIRouter(tags=["quotations"])


def dispatch(request, method, body=None, query=None):
    result = request.app.state.quotation_app.route(method, request.url.path, body or {}, query or {})
    status, payload, *extra = result
    if isinstance(payload, bytes):
        return Response(payload, status_code=status, headers=extra[0] if extra else {})
    return JSONResponse(payload, status_code=status)


@router.get("/api/health")
def health(request: Request):
    return dispatch(request, "GET")


@router.get("/api/enquiries/{enquiry_id}/quotation")
def enquiry_quotation(enquiry_id: str, request: Request):
    return dispatch(request, "GET")


@router.get("/api/enquiries/{enquiry_id}/activity")
def enquiry_activity(enquiry_id: UUID, request: Request):
    return {"items": get_enquiry(enquiry_id, request).activity}


@router.get("/api/quotations/{quotation_id}/activity")
def quotation_activity(quotation_id: UUID, request: Request):
    quote = request.app.state.quotation_app.quotations.get(quotation_id.hex)
    return {"items": get_enquiry(UUID(quote["enquiryId"]), request).activity}


@router.post("/api/demo/enquiries")
def demo_enquiry(request: Request, body: dict = Body(...)):
    return dispatch(request, "POST", body)
