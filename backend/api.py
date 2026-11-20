from fastapi import APIRouter, Query, HTTPException, Response
from typing import List
from data.edgar import CompanyFiling, EdgarError, EdgarNotFound, download_annual_filing, fetch_annual_filings
from data.market_data import fetch_stock_data, MarketDataError
from graph_engine import StockGraph, CompanyNode, RelationEdge
from database import init_db, SessionLocal, CompanyDB, RelationDB, ProductDB
from local_model import LocalModelResponseError, LocalModelTimeout, LocalModelUnavailable
from workflows.company_report import CompanyAnalysisResponse, company_report_workflow

router = APIRouter(prefix="/api")
graph = StockGraph()

def init_and_load_graph():
    init_db()
    db = SessionLocal()
    try:
        if db.query(CompanyDB).count() == 0:
            db.add_all([
                CompanyDB(ticker="NVDA", name="NVIDIA Corp.", sector="Półprzewodniki", market="US", score=9.2),
                CompanyDB(ticker="TSM", name="TSMC", sector="Półprzewodniki", market="US", score=8.8),
                CompanyDB(ticker="ASML", name="ASML Holding", sector="Półprzewodniki", market="US", score=8.5),
                CompanyDB(ticker="AMD", name="Advanced Micro Devices", sector="Półprzewodniki", market="US", score=8.4),
            ])
            db.add_all([
                ProductDB(company_ticker="NVDA", name="GPU", revenue_share_pct=85.0),
                ProductDB(company_ticker="NVDA", name="Układy AI"),
                ProductDB(company_ticker="TSM", name="Wafery krzemowe", revenue_share_pct=90.0),
                ProductDB(company_ticker="TSM", name="Litografia"),
                ProductDB(company_ticker="ASML", name="Maszyny EUV", revenue_share_pct=75.0),
                ProductDB(company_ticker="AMD", name="GPU", revenue_share_pct=70.0),
                ProductDB(company_ticker="AMD", name="Procesory serwerowe"),
            ])
            db.add_all([
                RelationDB(source_ticker="ASML", target_ticker="TSM", relation_type="DOSTAWCA", description="Dostarcza systemy litografii EUV"),
                RelationDB(source_ticker="TSM", target_ticker="NVDA", relation_type="DOSTAWCA", description="Produkuje układy GPU dla NVIDIA"),
                RelationDB(source_ticker="NVDA", target_ticker="AMD", relation_type="KONKURENT", description="Główny konkurent w segmencie GPU i AI"),
            ])
            db.commit()

        for c in db.query(CompanyDB).all():
            graph.add_company(CompanyNode(
                ticker=c.ticker,
                name=c.name,
                sector=c.sector,
                market=c.market,
                score=c.score,
                products=[p.name for p in c.products]
            ))
        for r in db.query(RelationDB).all():
            graph.add_relation(RelationEdge(
                source=r.source_ticker,
                target=r.target_ticker,
                relation_type=r.relation_type,
                weight=r.weight,
                description=r.description
            ))
    finally:
        db.close()

init_and_load_graph()

@router.get("/scenario1/search")
def search_by_phrase(phrase: str = Query(..., description="Np. półprzewodniki")):
    matched_companies = graph.search_and_sort_by_phrase(phrase.strip())
    tickers = [c.ticker for c in matched_companies]
    return {
        "phrase": phrase,
        "ranking": matched_companies,
        "graph": graph.get_subgraph_for_tickers(tickers)
    }

@router.get("/scenario2/connections")
def analyze_connections(tickers: List[str] = Query(..., description="Lista tickerów USA, np. ASML, NVDA")):
    normalized = [t.strip().upper() for t in tickers]
    paths = []
    for i in range(len(normalized)):
        for j in range(i + 1, len(normalized)):
            path = (
                graph.find_connection_path(normalized[i], normalized[j])
                or graph.find_connection_path(normalized[j], normalized[i])
            )
            paths.append({
                "from": normalized[i],
                "to": normalized[j],
                "connected": path is not None,
                "path": path or []
            })
    return {
        "requested_tickers": normalized,
        "connections_analysis": paths,
        "graph": graph.get_subgraph_for_tickers(normalized)
    }

@router.get("/company/{ticker}")
def get_company_report(ticker: str):
    ticker_clean = ticker.strip().upper()
    node = graph.nodes.get(ticker_clean)

    try:
        financials = fetch_stock_data(ticker_clean)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "ticker": financials["symbol"],
        "graph_profile": node,
        "market_data": financials
    }


@router.get("/company/{ticker}/filings")
def list_company_filings(ticker: str, limit: int = Query(default=5, ge=1, le=20)) -> list[CompanyFiling]:
    """List recent annual 10-K and 20-F filings from SEC EDGAR."""
    try:
        return fetch_annual_filings(ticker, limit)
    except EdgarNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EdgarError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get(
    "/company/{ticker}/filings/download",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}},
)
def download_company_filing(ticker: str, accession_number: str | None = None) -> Response:
    """Download a specific annual filing or the latest one if no accession number is provided."""
    try:
        filing, document = download_annual_filing(ticker, accession_number)
    except EdgarNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EdgarError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(
        content=document,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filing.primary_document}"'},
    )


@router.post("/company/{ticker}/analysis", response_model=CompanyAnalysisResponse)
def generate_company_report(ticker: str) -> CompanyAnalysisResponse:
    """Generate a company analysis in Polish using the local model."""
    try:
        return company_report_workflow.invoke({"ticker": ticker})["report"]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (MarketDataError, LocalModelResponseError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LocalModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LocalModelTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
