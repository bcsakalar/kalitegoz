"""Bilgi bankasi (RAG): parcalama, benzerlik ve arama testleri."""

import pytest

from app.services import knowledge


def test_chunk_text_splits_with_overlap():
    text = "\n\n".join(f"Paragraf {i}. " + ("kelime " * 60) for i in range(6))
    chunks = knowledge.chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= knowledge.CHUNK_CHARS + 50 for c in chunks)
    assert all(c.strip() for c in chunks)


def test_chunk_text_empty():
    assert knowledge.chunk_text("   ") == []


def test_cosine_similarity():
    assert knowledge.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert knowledge.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert knowledge.cosine([1, 0], []) == 0.0


def test_extract_text_md_and_unsupported():
    assert "merhaba" in knowledge.extract_text("a.md", b"# Baslik\nmerhaba")
    with pytest.raises(knowledge.KnowledgeError):
        knowledge.extract_text("a.xlsx", b"x")


def test_search_ranks_relevant_chunk_first(seeded, monkeypatch):
    """Embedding sahtelenir; arama en ilgili parcayi ustte dondurmeli."""
    from app.models import KnowledgeChunk, KnowledgeDoc
    from tests.conftest import TestingSession

    db = TestingSession()
    try:
        doc = KnowledgeDoc(tenant_id=seeded["tenant_a"], title="Prosedur",
                           source_filename="p.md", chunk_count=2)
        db.add(doc)
        db.flush()
        # Basit 2 boyutlu vektorler: [iade, kargo]
        db.add(KnowledgeChunk(tenant_id=seeded["tenant_a"], doc_id=doc.id, idx=0,
                              content="Iade suresi 14 gundur.", embedding=[1.0, 0.0]))
        db.add(KnowledgeChunk(tenant_id=seeded["tenant_a"], doc_id=doc.id, idx=1,
                              content="Kargo ucreti sirkete aittir.", embedding=[0.0, 1.0]))
        db.commit()

        monkeypatch.setattr(knowledge, "embed", lambda texts, ts=None: [[1.0, 0.0]])
        hits = knowledge.search(db, seeded["tenant_a"], "iade suresi kac gun")
        assert hits, "en az bir sonuc bekleniyor"
        assert "14 gun" in hits[0][0].content
    finally:
        db.close()


def test_search_is_tenant_scoped(seeded, monkeypatch):
    """Bir tenant'in dokumani baska tenant'in aramasinda cikmamali."""
    from app.models import KnowledgeChunk, KnowledgeDoc
    from tests.conftest import TestingSession

    db = TestingSession()
    try:
        doc = KnowledgeDoc(tenant_id=seeded["tenant_a"], title="Gizli", source_filename="g.md",
                           chunk_count=1)
        db.add(doc)
        db.flush()
        db.add(KnowledgeChunk(tenant_id=seeded["tenant_a"], doc_id=doc.id, idx=0,
                              content="A tenant gizli bilgi", embedding=[1.0, 0.0]))
        db.commit()

        monkeypatch.setattr(knowledge, "embed", lambda texts, ts=None: [[1.0, 0.0]])
        assert knowledge.search(db, seeded["tenant_b"], "gizli") == []
        assert len(knowledge.search(db, seeded["tenant_a"], "gizli")) == 1
    finally:
        db.close()


def test_build_context_empty_when_no_docs(seeded):
    from tests.conftest import TestingSession

    db = TestingSession()
    try:
        assert knowledge.build_context(db, seeded["tenant_a"], "herhangi bir transkript") == ""
    finally:
        db.close()
