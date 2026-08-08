"""Test altyapisi: SQLite in-memory DB + iki tenant'li ornek veri.

Uygulama lifespan'i (postgres + seed) TestClient'i `with` disinda kullanarak
tetiklenmez; sema ve tohum burada elle kurulur.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET", "test-secret")

from app import db as db_module  # noqa: E402
from app.db import Base  # noqa: E402
from app.deps import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Agent,
    BannedWord,
    Call,
    CallStatus,
    Channel,
    Criterion,
    Role,
    Team,
    Tenant,
    User,
)
from app.security import create_access_token, hash_password  # noqa: E402

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def seeded():
    """Her test icin temiz sema + iki tenant. Doner: onemli id sozlugu."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    ids = {}
    try:
        # --- Tenant A ---
        ta = Tenant(name="Tenant A", slug="a")
        tb = Tenant(name="Tenant B", slug="b")
        db.add_all([ta, tb])
        db.flush()
        ids["tenant_a"], ids["tenant_b"] = ta.id, tb.id

        # Tenant A'da iki takim: supervizor kapsamini test etmek icin
        team1 = Team(tenant_id=ta.id, name="Takim 1")
        team2 = Team(tenant_id=ta.id, name="Takim 2")
        db.add_all([team1, team2])
        db.flush()
        ids["team1"], ids["team2"] = team1.id, team2.id

        agent_a = Agent(tenant_id=ta.id, name="agent.a", team_id=team1.id)
        agent_other_team = Agent(tenant_id=ta.id, name="agent.other", team_id=team2.id)
        agent_b = Agent(tenant_id=tb.id, name="agent.b")
        db.add_all([agent_a, agent_other_team, agent_b])
        db.flush()
        ids["agent_a"], ids["agent_b"] = agent_a.id, agent_b.id
        ids["agent_other_team"] = agent_other_team.id

        admin_a = User(tenant_id=ta.id, email="admin@a", name="Admin A",
                       password_hash=hash_password("x"), role=Role.admin)
        agent_user_a = User(tenant_id=ta.id, email="agent@a", name="Agent A",
                            password_hash=hash_password("x"), role=Role.agent, agent_id=agent_a.id)
        sup_user_a = User(tenant_id=ta.id, email="sup@a", name="Supervisor A",
                          password_hash=hash_password("x"), role=Role.supervisor, team_id=team1.id)
        admin_b = User(tenant_id=tb.id, email="admin@b", name="Admin B",
                       password_hash=hash_password("x"), role=Role.admin)
        db.add_all([admin_a, agent_user_a, sup_user_a, admin_b])
        db.flush()
        ids["admin_a"], ids["agent_user_a"], ids["admin_b"] = admin_a.id, agent_user_a.id, admin_b.id
        ids["sup_user_a"] = sup_user_a.id

        db.add(Criterion(tenant_id=ta.id, name="Acilis", description="tanitim", group="Acilis"))
        db.add(BannedWord(tenant_id=ta.id, term="saçmalama", category="hakaret",
                          severity="yuksek", match_type="fuzzy"))

        # Tenant A'da iki cagri (farkli takimlar), Tenant B'de bir cagri
        call_a = Call(tenant_id=ta.id, filename="a.wav", audio_path="", channel=Channel.voice,
                      agent_id=agent_a.id, status=CallStatus.done, total_score=80.0)
        call_other_team = Call(tenant_id=ta.id, filename="other.wav", audio_path="",
                               channel=Channel.voice, agent_id=agent_other_team.id,
                               status=CallStatus.done, total_score=75.0)
        call_b = Call(tenant_id=tb.id, filename="b.wav", audio_path="", channel=Channel.voice,
                      agent_id=agent_b.id, status=CallStatus.done, total_score=70.0)
        db.add_all([call_a, call_other_team, call_b])
        db.flush()
        ids["call_a"], ids["call_b"] = call_a.id, call_b.id
        ids["call_other_team"] = call_other_team.id
        db.commit()
    finally:
        db.close()

    app.dependency_overrides[db_module.get_db] = _override_get_db
    yield ids
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def token_for(user_id: int, tenant_id: int, role: str) -> dict:
    tok = create_access_token(user_id, tenant_id, role)
    return {"Authorization": f"Bearer {tok}"}
