"""Reduce collective_name length

Revision ID: 46f5b94b2d2e
Revises: 37e23d2199a0
Create Date: 2022-06-03 05:00:26.602869

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "46f5b94b2d2e"
down_revision = "37e23d2199a0"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "author",
        "collective_name",
        existing_type=sa.VARCHAR(length=3000),
        type_=sa.String(length=2700),
        existing_nullable=True,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "author",
        "collective_name",
        existing_type=sa.String(length=2700),
        type_=sa.VARCHAR(length=3000),
        existing_nullable=True,
    )
    # ### end Alembic commands ###
