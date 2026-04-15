"""
Comic Vine API client.
Docs: https://comicvine.gamespot.com/api/documentation
Free API key required — register at https://comicvine.gamespot.com/api/

Two-phase search flow:
  Phase 1 — search_volumes(name):  search /volumes/ by series title
  Phase 2 — search_volume_issues(volume_id): get issues for a specific volume,
             optionally filtered by issue_number
"""
import logging
from typing import List, Dict, Tuple

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://comicvine.gamespot.com/api"
_VOLUME_FIELDS = "id,name,publisher,start_year,image,site_detail_url,count_of_issues"
_ISSUE_FIELDS = (
    "id,name,issue_number,volume,cover_date,image,"
    "person_credits,site_detail_url"
)

_HEADERS = {
    "User-Agent": "CollectiblesManager/1.0",
    "Accept": "application/json",
}


def _extract_credits(person_credits: list, role: str) -> str:
    """Return comma-separated people matching the given role."""
    if not person_credits:
        return ""
    names = [p.get("name", "") for p in person_credits if role.lower() in (p.get("role") or "").lower()]
    return ", ".join(n for n in names if n)


def _normalize_volume(vol: dict) -> Dict:
    """Convert a Comic Vine volume dict to the app's flat card format."""
    publisher = vol.get("publisher") or {}
    publisher_name = publisher.get("name", "") if isinstance(publisher, dict) else ""

    image = vol.get("image") or {}
    image_url = (
        image.get("medium_url")
        or image.get("small_url")
        or image.get("original_url")
        or ""
    )

    return {
        "game": "Comics",
        "name": vol.get("name", ""),
        "set": publisher_name,                       # publisher → set_name
        "set_code": str(vol.get("id", "")),          # volume_id → used to fetch issues
        "card_number": str(vol.get("count_of_issues") or ""),  # issue count for display
        "year": str(vol.get("start_year") or ""),
        "image_url": image_url,
        "link": vol.get("site_detail_url", ""),
        "price_usd": 0.0,
        "source": "Comic Vine",
        "artist": "",
        "comic_artist": "",
        "issue_number": "",
        "story_arc": "",
        "writer": "",
        "publisher": publisher_name,
        "is_key_issue": False,
        "cgc_cert_number": "",
    }


def _normalize_issue(issue: dict) -> Dict:
    """Convert a Comic Vine issue dict to the app's flat card format."""
    volume = issue.get("volume") or {}

    image = issue.get("image") or {}
    image_url = (
        image.get("medium_url")
        or image.get("small_url")
        or image.get("original_url")
        or ""
    )

    cover_date = issue.get("cover_date") or ""
    year = cover_date[:4] if cover_date else ""

    person_credits = issue.get("person_credits") or []
    writer = _extract_credits(person_credits, "writer")
    artist = _extract_credits(person_credits, "penciler") or _extract_credits(person_credits, "artist")

    return {
        "game": "Comics",
        "name": volume.get("name", ""),              # series title as primary name
        "set": volume.get("name", ""),               # series/volume → set_name
        "set_code": str(volume.get("id", "")),       # volume_id
        "card_number": "",
        "year": year,
        "image_url": image_url,
        "link": issue.get("site_detail_url", ""),
        "price_usd": 0.0,
        "source": "Comic Vine",
        "artist": artist,
        "comic_artist": artist,
        "issue_number": str(issue.get("issue_number") or ""),
        "story_arc": issue.get("name") or "",        # issue title → story arc
        "writer": writer,
        "publisher": "",                             # not returned on individual issues
        "is_key_issue": False,
        "cgc_cert_number": "",
    }


def search_volumes(
    name: str,
    api_key: str = "",
    page_size: int = 25,
) -> Tuple[List[Dict], int, int, str]:
    """
    Phase 1: Search for comic series/volumes by title.

    Returns (volumes, shown, total, source_label) where each item
    represents a series (e.g. "Action Comics") the user can browse into.
    """
    if not api_key:
        return [], 0, 0, "Comic Vine (no API key — add COMIC_VINE_API_KEY to backend/.env)"

    name = (name or "").strip()
    if not name:
        return [], 0, 0, "Comic Vine (no search term)"

    try:
        params = {
            "api_key": api_key,
            "format": "json",
            "filter": f"name:{name}",
            "field_list": _VOLUME_FIELDS,
            "limit": page_size,
            "offset": 0,
            "sort": "name:asc",
        }
        resp = requests.get(f"{_BASE_URL}/volumes/", params=params, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        status_code = data.get("status_code", 1)
        if status_code != 1:
            error = data.get("error", "Unknown error")
            logger.warning("Comic Vine volumes error %s: %s", status_code, error)
            return [], 0, 0, f"Comic Vine Error: {error}"

        results = data.get("results") or []
        total = data.get("number_of_total_results", len(results))
        volumes = [_normalize_volume(v) for v in results]

        logger.debug("Comic Vine volumes: %d results for %r", len(volumes), name)
        return volumes, len(volumes), total, "Comic Vine"

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            return [], 0, 0, "Comic Vine (invalid API key)"
        logger.error("Comic Vine volumes HTTP error: %s", e)
        return [], 0, 0, f"Comic Vine Error: {str(e)}"
    except Exception as e:
        logger.error("Comic Vine volumes error: %s", e)
        return [], 0, 0, f"Comic Vine Error: {str(e)}"


def search_volume_issues(
    volume_id: str,
    issue_number: str = "",
    api_key: str = "",
    page_size: int = 50,
) -> Tuple[List[Dict], int, int, str]:
    """
    Phase 2: Get all issues for a specific volume (series).

    When issue_number is provided, returns only that issue.
    Results are sorted by issue number ascending.
    """
    if not api_key:
        return [], 0, 0, "Comic Vine (no API key)"

    if not volume_id:
        return [], 0, 0, "Comic Vine (no volume selected)"

    try:
        filter_str = f"volume:{volume_id}"
        if issue_number.strip():
            filter_str += f",issue_number:{issue_number.strip()}"

        params = {
            "api_key": api_key,
            "format": "json",
            "filter": filter_str,
            "field_list": _ISSUE_FIELDS,
            "limit": page_size,
            "offset": 0,
            "sort": "issue_number:asc",
        }
        resp = requests.get(f"{_BASE_URL}/issues/", params=params, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        status_code = data.get("status_code", 1)
        if status_code != 1:
            error = data.get("error", "Unknown error")
            logger.warning("Comic Vine issues error %s: %s", status_code, error)
            return [], 0, 0, f"Comic Vine Error: {error}"

        results = data.get("results") or []
        total = data.get("number_of_total_results", len(results))
        issues = [_normalize_issue(r) for r in results]

        logger.debug("Comic Vine issues: %d for volume %s", len(issues), volume_id)
        return issues, len(issues), total, "Comic Vine"

    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            return [], 0, 0, "Comic Vine (invalid API key)"
        logger.error("Comic Vine issues HTTP error: %s", e)
        return [], 0, 0, f"Comic Vine Error: {str(e)}"
    except Exception as e:
        logger.error("Comic Vine issues error: %s", e)
        return [], 0, 0, f"Comic Vine Error: {str(e)}"


def find_issue_by_series_name(
    series_name: str,
    issue_number: str,
    api_key: str = "",
    max_volumes: int = 5,
) -> Tuple[List[Dict], int, int, str]:
    """
    Direct issue search: find a specific issue number across all volumes
    whose name matches series_name.

    Steps:
      1. Search volumes by series_name (up to max_volumes results).
      2. For each matching volume, fetch issues filtered by issue_number.
      3. Return all matching issues combined, preserving volume context.
    """
    if not api_key:
        return [], 0, 0, "Comic Vine (no API key — add COMIC_VINE_API_KEY to backend/.env)"

    series_name = (series_name or "").strip()
    issue_number = (issue_number or "").strip()
    if not series_name or not issue_number:
        return [], 0, 0, "Comic Vine (series name and issue number are both required)"

    # Step 1: find matching volumes
    try:
        vol_params = {
            "api_key": api_key,
            "format": "json",
            "filter": f"name:{series_name}",
            "field_list": "id,name,publisher,start_year",
            "limit": max_volumes,
            "offset": 0,
            "sort": "name:asc",
        }
        resp = requests.get(f"{_BASE_URL}/volumes/", params=vol_params, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        vol_data = resp.json()

        if vol_data.get("status_code", 1) != 1:
            error = vol_data.get("error", "Unknown error")
            return [], 0, 0, f"Comic Vine Error: {error}"

        volumes = vol_data.get("results") or []
    except Exception as e:
        logger.error("Comic Vine find-issue volume search error: %s", e)
        return [], 0, 0, f"Comic Vine Error: {str(e)}"

    if not volumes:
        return [], 0, 0, "Comic Vine"

    # Step 2: for each volume, fetch the specific issue number
    all_issues: List[Dict] = []
    for vol in volumes:
        vol_id = str(vol.get("id", ""))
        if not vol_id:
            continue
        try:
            iss_params = {
                "api_key": api_key,
                "format": "json",
                "filter": f"volume:{vol_id},issue_number:{issue_number}",
                "field_list": _ISSUE_FIELDS,
                "limit": 10,
                "offset": 0,
            }
            resp = requests.get(f"{_BASE_URL}/issues/", params=iss_params, headers=_HEADERS, timeout=30)
            resp.raise_for_status()
            iss_data = resp.json()

            if iss_data.get("status_code", 1) != 1:
                continue

            for issue in (iss_data.get("results") or []):
                normalized = _normalize_issue(issue)
                # Enrich with publisher from volume search since issues don't return it
                publisher = vol.get("publisher") or {}
                if isinstance(publisher, dict):
                    normalized["publisher"] = publisher.get("name", "")
                all_issues.append(normalized)

        except Exception as e:
            logger.warning("Comic Vine find-issue error for volume %s: %s", vol_id, e)
            continue

    logger.debug(
        "Comic Vine find-issue: %d issues for %r #%s across %d volumes",
        len(all_issues), series_name, issue_number, len(volumes),
    )
    return all_issues, len(all_issues), len(all_issues), "Comic Vine"
