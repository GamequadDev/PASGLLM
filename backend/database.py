import os
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://pasgllm:pasgllm_password@localhost:5432/pasgllm_db"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class CompanyDB(Base):
    __tablename__ = "companies"

    ticker = Column(String(16), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    sector = Column(String(64), index=True, nullable=False, default="Nieznany")
    market = Column(String(16), default="US", index=True)
    exchange = Column(String(64), nullable=True)
    score = Column(Float, default=0.0)
    llm_summary = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    products = relationship("ProductDB", back_populates="company", cascade="all, delete-orphan")
    snapshots = relationship("MarketSnapshotDB", back_populates="company", cascade="all, delete-orphan")
    financials = relationship("QuarterlyFinancialDB", back_populates="company", cascade="all, delete-orphan")
    news = relationship("NewsItemDB", back_populates="company", cascade="all, delete-orphan")


class RelationDB(Base):
    __tablename__ = "relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_ticker = Column(String(16), ForeignKey("companies.ticker"), index=True, nullable=False)
    target_ticker = Column(String(16), ForeignKey("companies.ticker"), index=True, nullable=False)
    relation_type = Column(String(32), nullable=False)
    weight = Column(Float, default=1.0)
    description = Column(Text, default="")
    source_url = Column(String(512), nullable=True)


class ProductDB(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_ticker = Column(String(16), ForeignKey("companies.ticker"), index=True, nullable=False)
    name = Column(String(128), index=True, nullable=False)
    revenue_share_pct = Column(Float, nullable=True)
    description = Column(Text, nullable=True)

    company = relationship("CompanyDB", back_populates="products")


class MarketSnapshotDB(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_ticker = Column(String(16), ForeignKey("companies.ticker"), index=True, nullable=False)
    session_date = Column(String(16), nullable=False)
    latest_session_price = Column(Float, nullable=True)
    session_change_pct = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)
    trailing_pe = Column(Float, nullable=True)
    revenue_qoq_pct = Column(Float, nullable=True)
    price_currency = Column(String(8), default="USD")
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    company = relationship("CompanyDB", back_populates="snapshots")


class QuarterlyFinancialDB(Base):
    __tablename__ = "quarterly_financials"
    __table_args__ = (
        UniqueConstraint("company_ticker", "period_end", name="uq_company_quarter"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_ticker = Column(String(16), ForeignKey("companies.ticker"), index=True, nullable=False)
    period_end = Column(String(16), nullable=False)
    revenue = Column(Float, nullable=True)
    net_income = Column(Float, nullable=True)
    currency = Column(String(8), default="USD")

    company = relationship("CompanyDB", back_populates="financials")


class NewsItemDB(Base):
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_ticker = Column(String(16), ForeignKey("companies.ticker"), index=True, nullable=False)
    title = Column(String(256), nullable=False)
    source_url = Column(String(512), nullable=False)
    published_at = Column(DateTime, nullable=True)
    sentiment = Column(String(16), default="NEUTRAL")
    weight = Column(Float, default=0.5)

    company = relationship("CompanyDB", back_populates="news")


def init_db():
    """Tworzenie tabel w PostgreSQL, jeśli jeszcze nie istnieją."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency do FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()