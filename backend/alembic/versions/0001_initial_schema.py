"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-01-01 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_regions_name"),
    )
    op.create_index("ix_regions_name", "regions", ["name"])

    op.create_table(
        "load_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("load_mw", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="synthetic"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("region_id", "timestamp", name="uq_load_region_timestamp"),
    )
    op.create_index("ix_load_region_timestamp", "load_observations", ["region_id", "timestamp"])

    op.create_table(
        "weather_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=False),
        sa.Column("humidity_percent", sa.Float(), nullable=False),
        sa.Column("precipitation", sa.Float(), nullable=False, server_default="0"),
        sa.Column("weather_code", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("region_id", "timestamp", name="uq_weather_region_timestamp"),
    )
    op.create_index("ix_weather_region_timestamp", "weather_observations", ["region_id", "timestamp"])

    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("model_type", sa.String(length=32), nullable=False),
        sa.Column("training_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("artifact_path", sa.String(length=256), nullable=True),
        sa.Column("feature_columns", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("version", name="uq_model_versions_version"),
    )
    op.create_index("ix_model_versions_version", "model_versions", ["version"])

    op.create_table(
        "forecasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_version_id", sa.Integer(), sa.ForeignKey("model_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_hours", sa.Integer(), nullable=False),
        sa.Column("predicted_load_mw", sa.Float(), nullable=False),
        sa.Column("lower_bound", sa.Float(), nullable=True),
        sa.Column("upper_bound", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "region_id", "model_version_id", "generated_at", "target_timestamp",
            name="uq_forecast_identity",
        ),
    )
    op.create_index("ix_forecast_target_timestamp", "forecasts", ["target_timestamp"])
    op.create_index("ix_forecast_generated_at", "forecasts", ["generated_at"])
    op.create_index("ix_forecast_model_version_id", "forecasts", ["model_version_id"])
    op.create_index("ix_forecast_region_id", "forecasts", ["region_id"])

    op.create_table(
        "forecast_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("forecast_id", sa.Integer(), sa.ForeignKey("forecasts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actual_load_mw", sa.Float(), nullable=False),
        sa.Column("absolute_error", sa.Float(), nullable=False),
        sa.Column("squared_error", sa.Float(), nullable=False),
        sa.Column("absolute_percentage_error", sa.Float(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("forecast_id", name="uq_forecast_score_forecast_id"),
    )


def downgrade() -> None:
    op.drop_table("forecast_scores")
    op.drop_table("forecasts")
    op.drop_table("model_versions")
    op.drop_table("weather_observations")
    op.drop_table("load_observations")
    op.drop_table("regions")
