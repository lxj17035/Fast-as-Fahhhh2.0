"""Expose Xinjie's service contract in the shared FastAPI application."""

from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.exc import SQLAlchemyError

from app.activity import optional_demo_actor, record_activity
from app.xinjie_store import Store
from backend.errors import AppError
from backend.pdf import PDFService
from backend.quotations import QuotationService
from backend.settings import SettingsService, require_profile

router = APIRouter(prefix="/api", tags=["quotations"])


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manual: StrictBool = False


@contextmanager
def services(request: Request):
    try:
        store = Store(request.app.state.engine)
        settings = SettingsService(store)
        yield store, settings, QuotationService(store, settings)
    except AppError as error:
        raise HTTPException(
            status_code=error.status,
            detail={"message": "Quotation request rejected", "fields": error.fields},
        ) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Quotation storage unavailable"
        ) from None


@router.get("/settings")
def get_settings(request: Request):
    with services(request) as (_, settings, _):
        return settings.get_settings()


@router.patch("/settings")
def patch_settings(request: Request, patch: dict = Body(...)):
    with services(request) as (_, settings, _):
        return settings.update_settings(patch)


@router.get("/business-profiles")
def get_business_profiles(request: Request):
    with services(request) as (_, settings, _):
        return settings.list_profiles()


@router.patch("/business-profiles/active")
def select_business_profile(request: Request, patch: dict = Body(...)):
    with services(request) as (_, settings, _):
        return settings.select_profile(patch)


@router.get("/business-profiles/{profile_id}")
def get_business_profile(profile_id: str, request: Request):
    with services(request) as (_, settings, _):
        return settings.get_profile(profile_id)


@router.patch("/business-profiles/{profile_id}")
def patch_business_profile(profile_id: str, request: Request, patch: dict = Body(...)):
    with services(request) as (_, settings, _):
        return settings.update_settings(patch, profile_id)


@router.get("/clients/{client_id}")
def get_client(client_id: str, request: Request):
    with services(request) as (_, settings, _):
        return settings.get_client(client_id)


@router.patch("/clients/{client_id}")
def patch_client(client_id: str, request: Request, patch: dict = Body(...)):
    with services(request) as (_, settings, _):
        return settings.update_client(client_id, patch)


@router.post("/enquiries/{enquiry_id}/draft")
def create_draft(enquiry_id: UUID, body: DraftRequest, request: Request):
    with services(request) as (store, settings, quotations):
        try:
            store.get("enquiries", str(enquiry_id))
            key = str(enquiry_id)
        except AppError as error:
            if error.status != 404:
                raise
            key = enquiry_id.hex
        require_profile(store.get("enquiries", key), settings.active_profile_id())
        return request.app.state.quotation_app.drafts.create(key, manual=body.manual)


@router.get("/quotations/{quotation_id}")
def get_quotation(quotation_id: UUID, request: Request):
    with services(request) as (_, settings, quotations):
        return require_profile(quotations.get(quotation_id.hex), settings.active_profile_id())


@router.patch("/quotations/{quotation_id}")
def patch_quotation(quotation_id: UUID, request: Request, patch: dict = Body(...)):
    actor = optional_demo_actor(request)
    with services(request) as (store, settings, quotations):
        with store.transaction():
            require_profile(quotations.get(quotation_id.hex), settings.active_profile_id())
            saved = quotations.update(quotation_id.hex, patch)
            record_activity(
                store.connection,
                enquiry_id=saved["enquiryId"],
                quotation_id=saved["id"],
                version=saved["version"],
                action="quotation_updated",
                result="saved",
                **actor,
            )
            return saved


@router.get("/quotations/{quotation_id}/pdf")
def get_pdf(
    quotation_id: UUID,
    request: Request,
    version: Annotated[int, Query(gt=0, le=2**31 - 1)],
):
    with services(request) as (store, settings, quotations):
        require_profile(quotations.get(quotation_id.hex), settings.active_profile_id())
        pdf, saved_version = PDFService(store, quotations).get(
            quotation_id.hex, version
        )
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "X-Quotation-Version": str(saved_version),
                "Content-Disposition": (
                    f'inline; filename="quotation-{quotation_id.hex}'
                    f'-v{saved_version}.pdf"'
                ),
                "Cache-Control": "no-store",
            },
        )
