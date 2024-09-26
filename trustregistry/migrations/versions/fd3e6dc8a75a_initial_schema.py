"""Initial schema

Revision ID: fd3e6dc8a75a
Revises:
Create Date: 2024-09-26 13:38:19.138285

"""
from typing import Sequence, Union
import trustregistry.list_type
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd3e6dc8a75a'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('actors',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('roles', trustregistry.list_type.StringList(), nullable=False),
    sa.Column('didcomm_invitation', sa.String(), nullable=True),
    sa.Column('did', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_actors_did'), 'actors', ['did'], unique=True)
    op.create_index(op.f('ix_actors_didcomm_invitation'), 'actors', ['didcomm_invitation'], unique=True)
    op.create_index(op.f('ix_actors_id'), 'actors', ['id'], unique=True)
    op.create_index(op.f('ix_actors_name'), 'actors', ['name'], unique=True)
    op.create_index(op.f('ix_actors_roles'), 'actors', ['roles'], unique=False)
    op.create_table('schemas',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('did', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schemas_did'), 'schemas', ['did'], unique=False)
    op.create_index(op.f('ix_schemas_id'), 'schemas', ['id'], unique=True)
    op.create_index(op.f('ix_schemas_name'), 'schemas', ['name'], unique=False)
    op.create_index(op.f('ix_schemas_version'), 'schemas', ['version'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_schemas_version'), table_name='schemas')
    op.drop_index(op.f('ix_schemas_name'), table_name='schemas')
    op.drop_index(op.f('ix_schemas_id'), table_name='schemas')
    op.drop_index(op.f('ix_schemas_did'), table_name='schemas')
    op.drop_table('schemas')
    op.drop_index(op.f('ix_actors_roles'), table_name='actors')
    op.drop_index(op.f('ix_actors_name'), table_name='actors')
    op.drop_index(op.f('ix_actors_id'), table_name='actors')
    op.drop_index(op.f('ix_actors_didcomm_invitation'), table_name='actors')
    op.drop_index(op.f('ix_actors_did'), table_name='actors')
    op.drop_table('actors')
    # ### end Alembic commands ###
