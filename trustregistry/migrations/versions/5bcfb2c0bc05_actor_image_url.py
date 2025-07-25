"""Actor image_url

Revision ID: 5bcfb2c0bc05
Revises: fd3e6dc8a75a
Create Date: 2024-09-26 15:03:08.338158

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5bcfb2c0bc05"
down_revision: str | None = "fd3e6dc8a75a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("actors", sa.Column("image_url", sa.String(), nullable=True))
    op.create_index(op.f("ix_actors_image_url"), "actors", ["image_url"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_actors_image_url"), table_name="actors")
    op.drop_column("actors", "image_url")
    # ### end Alembic commands ###
