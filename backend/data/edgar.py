"""Retrieve filings from the SEC EDGAR public data API."""

import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from http.client import HTTPException as HTTPProtocolError
from itertools import islice
from threading import Lock
from time import monotonic, sleep, time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data"
DEFAULT_USER_AGENT = "PASGLLM/0.1 (+https://github.com/GamequadDev/PASGLLM)"
ANNUAL_FORMS = frozenset({"10-K", "20-F"})
PROSPECTUS_FORMS = frozenset({"424B4", "S-1", "S-1/A"})
ACCESSION_PATTERN = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
FILENAME_PATTERN = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*")
_request_lock = Lock()
_last_request = 0.0


class EdgarError(RuntimeError):
    """The SEC request failed or returned malformed data."""


class EdgarNotFound(LookupError):
    """The ticker or requested annual report could not be found."""


@dataclass(frozen=True)
class CompanyFiling:
    cik: str
    accession_number: str
    form: str
    filing_date: str
    report_date: str | None
    primary_document: str
    source_url: str


def _fetch(url: str) -> bytes:
    global _last_request

    user_agent = os.getenv("SEC_USER_AGENT") or DEFAULT_USER_AGENT
    request = Request(url, headers={"User-Agent": user_agent})
    # Space out requests from concurrent FastAPI calls to respect SEC's rate limit.
    with _request_lock:
        delay = 0.11 - (monotonic() - _last_request)
        if delay > 0:
            sleep(delay)
        _last_request = monotonic()

    try:
        with urlopen(request, timeout=15) as response:
            return response.read()
    except HTTPError as exc:
        exc.close()
        raise EdgarError(f"SEC EDGAR returned HTTP {exc.code} for {url}.") from exc
    except (URLError, OSError, HTTPProtocolError) as exc:
        raise EdgarError("Could not retrieve data from SEC EDGAR.") from exc


@lru_cache(maxsize=128)
def _get_json(url: str, _cache_window: int) -> dict:
    try:
        data = json.loads(_fetch(url))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise EdgarError("SEC EDGAR returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise EdgarError("SEC EDGAR returned unexpected metadata.")
    return data


def _find_cik(ticker: str) -> int:
    symbol = ticker.strip().upper().replace(".", "-")
    if not symbol:
        raise EdgarNotFound("A ticker is required.")

    companies = _get_json(TICKERS_URL, int(time() // 86400))
    try:
        for company in companies.values():
            if company["ticker"].upper().replace(".", "-") == symbol:
                return int(company["cik_str"])
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise EdgarError("SEC EDGAR returned an invalid ticker directory.") from exc
    raise EdgarNotFound(f"Ticker {symbol} was not found in SEC EDGAR.")


def _submission_batches(cik: int) -> Iterator[dict]:
    data = _get_json(f"{SUBMISSIONS_URL}/CIK{cik:010d}.json", int(time() // 300))
    try:
        filings = data["filings"]
        yield filings["recent"]
        for archive in sorted(filings["files"], key=lambda file: file["filingTo"], reverse=True):
            filename = archive["name"]
            if not FILENAME_PATTERN.fullmatch(filename):
                raise ValueError("Invalid submissions archive filename.")
            yield _get_json(f"{SUBMISSIONS_URL}/{filename}", int(time() // 86400))
    except (KeyError, TypeError, ValueError) as exc:
        raise EdgarError("SEC EDGAR returned invalid submission metadata.") from exc


def _filings(ticker: str, forms: frozenset[str]) -> Iterator[CompanyFiling]:
    cik = _find_cik(ticker)
    for batch in _submission_batches(cik):
        try:
            rows = zip(
                batch["form"], batch["accessionNumber"], batch["filingDate"],
                batch["reportDate"], batch["primaryDocument"], strict=True,
            )
            for form, accession, filing_date, report_date, document in sorted(
                rows, key=lambda row: row[2], reverse=True,
            ):
                if form not in forms:
                    continue
                document = document or f"{accession}.txt"
                if not ACCESSION_PATTERN.fullmatch(accession) or not FILENAME_PATTERN.fullmatch(document):
                    raise ValueError("Invalid SEC report identifier or filename.")
                accession_dir = accession.replace("-", "")
                yield CompanyFiling(
                    cik=f"{cik:010d}",
                    accession_number=accession,
                    form=form,
                    filing_date=filing_date,
                    report_date=report_date or None,
                    primary_document=document,
                    source_url=f"{ARCHIVE_URL}/{cik}/{accession_dir}/{document}",
                )
        except (KeyError, TypeError, ValueError) as exc:
            raise EdgarError("SEC EDGAR returned invalid filing metadata.") from exc


def fetch_annual_filings(ticker: str, limit: int = 5) -> list[CompanyFiling]:
    return list(islice(_filings(ticker, ANNUAL_FORMS), limit))


def find_business_filing(ticker: str) -> CompanyFiling | None:
    """Prefer an annual report, then a final prospectus, then a registration statement."""
    prospectus = None
    for filing in _filings(ticker, ANNUAL_FORMS | PROSPECTUS_FORMS):
        if filing.form in ANNUAL_FORMS:
            return filing
        if prospectus is None or (filing.form == "424B4" and prospectus.form != "424B4"):
            prospectus = filing
    return prospectus


def fetch_filing_document(filing: CompanyFiling) -> bytes:
    return _fetch(filing.source_url)


def download_annual_filing(ticker: str, accession_number: str | None = None) -> tuple[CompanyFiling, bytes]:
    if accession_number is None or ACCESSION_PATTERN.fullmatch(accession_number):
        for filing in _filings(ticker, ANNUAL_FORMS):
            if accession_number is None or filing.accession_number == accession_number:
                return filing, fetch_filing_document(filing)
    raise EdgarNotFound("The requested annual filing was not found for this ticker.")
