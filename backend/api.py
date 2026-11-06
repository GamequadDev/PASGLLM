from fastapi import APIRouter, Query
from typing import List
from graph_engine import StockGraph, CompanyNode, RelationEdge

router = APIRouter(prefix="/api")
graph = StockGraph()

def seed_mock_data():
    companies = [
        CompanyNode(ticker="NVDA", name="NVIDIA Corp.", sector="Półprzewodniki", market="US", score=9.2, products=["GPU", "Układy AI"]),
        CompanyNode(ticker="TSM", name="TSMC", sector="Półprzewodniki", market="US", score=8.8, products=["Wafery krzemowe", "Litografia"]),
        CompanyNode(ticker="ASML", name="ASML Holding", sector="Półprzewodniki", market="EU", score=8.5, products=["Maszyny EUV"]),
        CompanyNode(ticker="VGO.WA", name="Vigo Photonics", sector="Półprzewodniki", market="PL", score=7.4, products=["Detektory podczerwieni"]),
    ]
    for c in companies:
        graph.add_company(c)

    relations = [
        RelationEdge(source="ASML", target="TSM", relation_type="DOSTAWCA", description="Dostarcza systemy litografii EUV"),
        RelationEdge(source="TSM", target="NVDA", relation_type="DOSTAWCA", description="Produkuje układy GPU dla NVIDIA"),
    ]
    for r in relations:
        graph.add_relation(r)

seed_mock_data()

@router.get("/scenario1/search")
def search_by_phrase(phrase: str = Query(..., description="Np. półprzewodniki")):
    matched_companies = graph.search_and_sort_by_phrase(phrase)
    tickers = [c.ticker for c in matched_companies]
    return {
        "phrase": phrase,
        "ranking": matched_companies,
        "graph": graph.get_subgraph_for_tickers(tickers)
    }

@router.get("/scenario2/connections")
def analyze_connections(tickers: List[str] = Query(..., description="Lista tickerów")):
    paths = []
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            path = graph.find_connection_path(tickers[i], tickers[j]) or graph.find_connection_path(tickers[j], tickers[i])
            paths.append({
                "from": tickers[i],
                "to": tickers[j],
                "connected": path is not None,
                "path": path or []
            })
    return {
        "requested_tickers": tickers,
        "connections_analysis": paths,
        "graph": graph.get_subgraph_for_tickers(tickers)
    }
