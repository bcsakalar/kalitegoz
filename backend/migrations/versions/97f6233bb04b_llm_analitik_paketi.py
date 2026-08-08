"""llm_analitik_paketi — Dalga 1

calls tablosuna LLM analitik alanlari: baskin duygu, duygu yorungesi,
duygu-sonuc uyumsuzlugu, sonraki aksiyon, churn riski, musteri efor (CES),
niyet etiketleri.

NOT: autogenerate BOS uretti cunku calisan api container'i (bind mount yok)
eski modelleri gorur; ayrica create_all mevcut tabloya SUTUN EKLEMEZ. Bu yuzden
migration elle yazildi. NOT NULL alanlar (emotion_mismatch, intent_tags) mevcut
satirlar icin server_default ile eklenir, sonra default kaldirilir — uygulama
kodu degeri kendisi verdigi icin kalici server_default gereksiz.

Revision ID: 97f6233bb04b
Revises: 9c5a1ea9766b
Create Date: 2026-07-16 19:15:41.832374
"""
from alembic import op
import sqlalchemy as sa


revision = '97f6233bb04b'
down_revision = '9c5a1ea9766b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable alanlar — dogrudan eklenebilir
    op.add_column('calls', sa.Column('emotion', sa.String(length=24), nullable=True))
    op.add_column('calls', sa.Column('sentiment_trajectory', sa.String(length=16), nullable=True))
    op.add_column('calls', sa.Column('next_action', sa.Text(), nullable=True))
    op.add_column('calls', sa.Column('churn_risk', sa.String(length=16), nullable=True))
    op.add_column('calls', sa.Column('customer_effort', sa.Float(), nullable=True))
    op.create_index(op.f('ix_calls_emotion'), 'calls', ['emotion'])
    op.create_index(op.f('ix_calls_churn_risk'), 'calls', ['churn_risk'])

    # NOT NULL boolean — mevcut satirlar icin gecici server_default
    op.add_column('calls', sa.Column(
        'emotion_mismatch', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('calls', 'emotion_mismatch', server_default=None)
    op.create_index(op.f('ix_calls_emotion_mismatch'), 'calls', ['emotion_mismatch'])

    # NOT NULL JSON — mevcut satirlar icin gecici bos liste
    op.add_column('calls', sa.Column(
        'intent_tags', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.alter_column('calls', 'intent_tags', server_default=None)


def downgrade() -> None:
    op.drop_column('calls', 'intent_tags')
    op.drop_index(op.f('ix_calls_emotion_mismatch'), table_name='calls')
    op.drop_column('calls', 'emotion_mismatch')
    op.drop_index(op.f('ix_calls_churn_risk'), table_name='calls')
    op.drop_index(op.f('ix_calls_emotion'), table_name='calls')
    op.drop_column('calls', 'customer_effort')
    op.drop_column('calls', 'churn_risk')
    op.drop_column('calls', 'next_action')
    op.drop_column('calls', 'sentiment_trajectory')
    op.drop_column('calls', 'emotion')
