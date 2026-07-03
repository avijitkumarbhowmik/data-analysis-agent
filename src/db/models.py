from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, Text, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    """A named analysis context the user returns to across days."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class Dataset(Base):
    """A file loaded into a workspace (Phase 1: one CSV under frame name ``df``)."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(
        Text, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)  # frame name used in code, e.g. "df"
    filename: Mapped[str] = mapped_column(Text, nullable=False)  # original upload filename
    file_path: Mapped[str] = mapped_column(Text, nullable=False)  # on-disk path
    sheet_name: Mapped[str | None] = mapped_column(Text, nullable=True)  # Excel sheet (Phase 3)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[list | None] = mapped_column(JSON, nullable=False, default=list)
    pii_columns_json: Mapped[list | None] = mapped_column(JSON, nullable=False, default=list)
    is_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )


class RunRow(Base):
    """One question and its full analysis trail — the persisted run history.

    The boilerplate shipped ``input_text``/``output_text``; Phase 1 keeps them
    (``input_text``=question, ``output_text``=answer) and adds the explicit
    columns the agent needs.
    """

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    workspace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Boilerplate legacy columns (kept in sync: input_text=question, output_text=answer)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_preview: Mapped[str | None] = mapped_column(Text, nullable=True)  # masked; the LLM audit trail
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    chart_spec_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_quality_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    followups_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    cost_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
