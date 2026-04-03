"""
Lookup endpoints for barcode and other external data lookups.
GET /api/lookup/upc?code=<barcode>
GET /api/lookup/images?q=<query>
"""
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/lookup", tags=["lookup"])


class PsaCertResult(BaseModel):
    player: str = ""
    year: str = ""
    brand: str = ""
    set_name: str = ""
    card_number: str = ""
    grade: str = ""
    subject: str = ""


class UpcResult(BaseModel):
    name: str
    manufacturer: str = ""
    description: str = ""
    image_url: str = ""
    price: Optional[float] = None
    upc: str
    category: str = ""


class ImageResult(BaseModel):
    url: str
    thumbnail: str
    title: str
    source: str


class ImageSearchResponse(BaseModel):
    results: List[ImageResult]
    query: str
    configured: bool   # False = no API keys set, frontend shows fallback


@router.get("/psa/{cert_number}", response_model=PsaCertResult)
def lookup_psa_endpoint(cert_number: str):
    """Look up a PSA cert number and return card details."""
    from ..external.psa import lookup_psa_cert
    result = lookup_psa_cert(cert_number)
    if result is None:
        raise HTTPException(status_code=404, detail="PSA cert not found.")
    return PsaCertResult(
        player=result["player"],
        year=result["year"],
        brand=result["brand"],
        set_name=result["set_name"],
        card_number=result["card_number"],
        grade=result["grade"],
        subject=result["subject"],
    )


@router.get("/upc", response_model=UpcResult)
def lookup_upc_endpoint(
    code: str = Query(..., description="UPC or EAN barcode"),
):
    """Look up a product by barcode using UPCitemdb. Returns name, brand, image, price."""
    from ..external.upcitemdb import lookup_upc
    from ..config import settings

    result = lookup_upc(code, api_key=settings.upcitemdb_api_key)
    if result is None:
        raise HTTPException(status_code=404, detail="No product found for that barcode.")

    return UpcResult(**result)


@router.get("/images", response_model=ImageSearchResponse)
def image_search_endpoint(
    q: str = Query(..., description="Search query"),
    num: int = Query(10, ge=1, le=10, description="Number of results (max 10)"),
):
    """Search for images using Google Custom Search JSON API."""
    from ..external.image_search import search_images
    from ..config import settings

    configured = bool(settings.serpapi_key)

    if not configured:
        return ImageSearchResponse(results=[], query=q, configured=False)

    try:
        raw = search_images(q, api_key=settings.serpapi_key, num=num)
        results = [ImageResult(**r) for r in raw]
        return ImageSearchResponse(results=results, query=q, configured=True)
    except Exception as e:
        detail = str(e)
        if "quota" in detail.lower() or "429" in detail or "rate" in detail.lower():
            raise HTTPException(status_code=429, detail="Monthly image search quota reached (250/month). Try again next month.")
        raise HTTPException(status_code=502, detail=f"Image search error: {detail}")
