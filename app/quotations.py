"""Quotation routes sharing the Telegram application's database engine."""
from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse, Response

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


@router.get("/api/settings")
def read_settings(request: Request):
    return dispatch(request, "GET")


@router.get("/api/clients/{client_id}")
def read_client(client_id: str, request: Request):
    return dispatch(request, "GET")


@router.get("/api/quotations/{quotation_id}")
def read_quotation(quotation_id: str, request: Request):
    return dispatch(request, "GET")


@router.get("/api/enquiries/{enquiry_id}/quotation")
def enquiry_quotation(enquiry_id: str, request: Request):
    return dispatch(request, "GET")


@router.get("/api/enquiries/{enquiry_id}/activity")
def enquiry_activity(enquiry_id: str, request: Request):
    return dispatch(request, "GET")


@router.get("/api/quotations/{quotation_id}/activity")
def quotation_activity(quotation_id: str, request: Request):
    return dispatch(request, "GET")


@router.patch("/api/settings")
def edit_settings(request: Request, body: dict = Body(...)):
    return dispatch(request, "PATCH", body)


@router.patch("/api/clients/{client_id}")
def edit_client(client_id: str, request: Request, body: dict = Body(...)):
    return dispatch(request, "PATCH", body)


@router.patch("/api/quotations/{quotation_id}")
def edit_quotation(quotation_id: str, request: Request, body: dict = Body(...)):
    return dispatch(request, "PATCH", body)


@router.post("/api/demo/enquiries")
def demo_enquiry(request: Request, body: dict = Body(...)):
    return dispatch(request, "POST", body)


@router.post("/api/enquiries/{enquiry_id}/draft")
def draft(enquiry_id: str, request: Request, body: dict = Body(...)):
    return dispatch(request, "POST", body)


@router.post("/api/quotations/{quotation_id}/send")
def send(quotation_id: str, request: Request, body: dict = Body(...)):
    return dispatch(request, "POST", body)


@router.get("/api/quotations/{quotation_id}/pdf")
def preview(quotation_id: str, request: Request, version: int | None = Query(default=None, ge=1)):
    return dispatch(request, "GET", query={"version": [str(version)]} if version is not None else {})
