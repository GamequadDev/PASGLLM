from fastapi import APIRouter, Query, HTTPException
from typing import List
from market_data import fetch_stock_data, MarketDataError
from graph_engine import StockGraph, CompanyNode, RelationEdge

router = APIRouter(prefix="/api")
graph = StockGraph()

def seed_mock_data():
    companies = [
        CompanyNode(ticker="NVDA", name="NVIDIA Corp.", sector="Półprzewodniki", market="US", score=9.2, products=["GPU", "Układy AI"]),
        CompanyNode(ticker="TSM", name="TSMC", sector="Półprzewodniki", market="US", score=8.8, products=["Wafery krzemowe", "Litografia"]),
        CompanyNode(ticker="ASML", name="ASML Holding", sector="Półprzewodniki", market="US", score=8.5, products=["Maszyny EUV"]),
        CompanyNode(ticker="AMD", name="Advanced Micro Devices", sector="Półprzewodniki", market="US", score=8.4, products=["GPU", "Procesory serwerowe"]),
    ]
    for c in companies:
        graph.add_company(c)

    relations = [
        RelationEdge(source="ASML", target="TSM", relation_type="DOSTAWCA", description="Dostarcza systemy litografii EUV"),
        RelationEdge(source="TSM", target="NVDA", relation_type="DOSTAWCA", description="Produkuje układy GPU dla NVIDIA"),
        RelationEdge(source="NVDA", target="AMD", relation_type="KONKURENT", description="Główny konkurent w segmencie GPU i AI"),
    ]
    for r in relations:
        graph.add_relation(r)

seed_mock_data()

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