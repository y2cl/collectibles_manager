"""
PSA Public Cert Lookup
Uses the PSA public API (no auth required).
https://api.psacard.com/publicapi/cert/GetByCertNumber/{certNumber}
"""
import requests
from typing import Optional, Dict, Any

PSA_API_URL = "https://api.psacard.com/publicapi/cert/GetByCertNumber/{cert}"


def lookup_psa_cert(cert_number: str) -> Optional[Dict[str, Any]]:
    """
    Fetch cert details from PSA public API.
    Returns a normalized dict or None if not found.
    """
    url = PSA_API_URL.format(cert=cert_number.strip())
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None

    # PSA returns {"PSACert": {...}} or {"CertDetails": {...}} depending on endpoint version
    cert = data.get("PSACert") or data.get("CertDetails") or data
    if not cert:
        return None

    # Normalize fields
    subject = cert.get("Subject", "") or ""          # e.g. "1952 Topps Mickey Mantle #311"
    year = cert.get("Year", "") or ""
    brand = cert.get("Brand", "") or ""              # manufacturer/brand
    set_name = cert.get("CardSet", "") or cert.get("Set", "") or ""
    card_number = cert.get("CardNumber", "") or ""
    grade = cert.get("CardGrade", "") or cert.get("Grade", "") or ""
    player = cert.get("Subject", "") or cert.get("Player", "") or ""

    # Try to parse year from subject if not returned directly
    if not year and subject:
        parts = subject.split()
        if parts and parts[0].isdigit() and len(parts[0]) == 4:
            year = parts[0]

    return {
        "player": player,
        "year": year,
        "brand": brand,
        "set_name": set_name,
        "card_number": card_number,
        "grade": grade,
        "subject": subject,
        "raw": cert,
    }
