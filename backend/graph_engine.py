from collections import deque
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class CompanyNode(BaseModel):
    ticker: str
    name: str
    sector: str
    market: str  # np. "US", "PL"
    score: float = 0.0  # Ocena kondycji wyliczona z danych / LLM
    products: List[str] = []

class RelationEdge(BaseModel):
    source: str       # ticker spółki A
    target: str       # ticker spółki B
    relation_type: str # np. "KAPITAŁOWE", "DOSTAWCA", "KLIENT"
    weight: float = 1.0
    description: str = ""

class StockGraph:
    def __init__(self):
        self.nodes: Dict[str, CompanyNode] = {}
        self.adj_list: Dict[str, List[RelationEdge]] = {}

    def add_company(self, company: CompanyNode):
        self.nodes[company.ticker] = company
        if company.ticker not in self.adj_list:
            self.adj_list[company.ticker] = []

    def add_relation(self, edge: RelationEdge):
        if edge.source in self.nodes and edge.target in self.nodes:
            self.adj_list[edge.source].append(edge)

    def search_and_sort_by_phrase(self, phrase: str) -> List[CompanyNode]:
        """Scenariusz 1: Wyszukiwanie spółek po frazie (sektor/produkty) i sortowanie malejąco wg oceny."""
        phrase_lower = phrase.lower()
        matched = [
            node for node in self.nodes.values()
            if phrase_lower in node.sector.lower()
            or any(phrase_lower in prod.lower() for prod in node.products)
        ]
        return sorted(matched, key=lambda x: x.score, reverse=True)

    def find_connection_path(self, start_ticker: str, end_ticker: str) -> Optional[List[str]]:
        """Scenariusz 2: Algorytm BFS szukający ścieżki powiązań między dwiema spółkami."""
        if start_ticker not in self.nodes or end_ticker not in self.nodes:
            return None

        queue = deque([[start_ticker]])
        visited = {start_ticker}

        while queue:
            path = queue.popleft()
            current = path[-1]

            if current == end_ticker:
                return path

            for edge in self.adj_list.get(current, []):
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append(path + [edge.target])
        return None

    def get_subgraph_for_tickers(self, tickers: List[str]) -> Dict[str, Any]:
        """Zwraca wycinek grafu (węzły i krawędzie) do wizualizacji."""
        ticker_set = set(tickers)
        sub_nodes = [self.nodes[t] for t in tickers if t in self.nodes]
        sub_edges = [
            edge for t in tickers
            for edge in self.adj_list.get(t, [])
            if edge.target in ticker_set
        ]
        return {"nodes": sub_nodes, "edges": sub_edges}
