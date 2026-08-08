"""kurumsal_marka_kolonlari — Dalga 13 (satilabilir MVP)

tenants tablosuna beyaz etiket (white-label) alanlari: marka adi, ana renk, logo.
Hepsi nullable — bos ise config varsayilanlari (BRAND_NAME/BRAND_COLOR) kullanilir.

Diger kurumsal ozellikler (PII maskeleme okuma-aninda, denetim gunlugu, SSO,
AI puan karti, ROI, push-ingest) SEMA DEGISIKLIGI GEREKTIRMEZ — mevcut tablolari
(audit_logs, criteria) ve config'i kullanir. Yalnizca bu 3 kolon yeni.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("brand_name", sa.String(length=80), nullable=True))
    op.add_column("tenants", sa.Column("brand_color", sa.String(length=9), nullable=True))
    op.add_column("tenants", sa.Column("logo_data_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "logo_data_url")
    op.drop_column("tenants", "brand_color")
    op.drop_column("tenants", "brand_name")
