"""Schema type

Revision ID: eabeefe99e00
Revises: 5bcfb2c0bc05
Create Date: 2025-03-20 10:15:10.983023

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eabeefe99e00"
down_revision: Union[str, None] = "5bcfb2c0bc05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("schemas", sa.Column("schema_type", sa.String(), nullable=False, server_default="indy"))
    op.create_index(
        op.f("ix_schemas_schema_type"), "schemas", ["schema_type"], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_schemas_schema_type"), table_name="schemas")
    op.drop_column("schemas", "schema_type")
    # ### end Alembic commands ###
