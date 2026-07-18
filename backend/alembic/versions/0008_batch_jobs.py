"""add local batch jobs

Revision ID: 0008_batch_jobs
Revises: 0007_stored_files
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_batch_jobs"
down_revision = "0007_stored_files"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("batch_jobs", sa.Column("id", sa.String(64), primary_key=True), sa.Column("api_token_id", sa.Integer(), sa.ForeignKey("api_tokens.id"), nullable=True), sa.Column("input_file_id", sa.String(64), sa.ForeignKey("stored_files.id"), nullable=False), sa.Column("output_file_id", sa.String(64), sa.ForeignKey("stored_files.id"), nullable=True), sa.Column("endpoint", sa.String(128), nullable=False), sa.Column("completion_window", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("request_counts_json", sa.JSON(), nullable=True), sa.Column("error_message", sa.Text(), nullable=True), sa.Column("cancelled_at", sa.DateTime(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_batch_jobs_api_token_id", "batch_jobs", ["api_token_id"])
    op.create_index("ix_batch_jobs_input_file_id", "batch_jobs", ["input_file_id"])
    op.create_index("ix_batch_jobs_status", "batch_jobs", ["status"])
def downgrade() -> None: op.drop_table("batch_jobs")
