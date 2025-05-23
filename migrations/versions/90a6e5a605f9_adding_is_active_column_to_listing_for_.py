"""adding is_active column to listing for expiring links

Revision ID: 90a6e5a605f9
Revises: c7ac570c97ca
Create Date: 2025-05-15 12:51:57.185502

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '90a6e5a605f9'
down_revision = 'c7ac570c97ca'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('listing', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('listing', schema=None) as batch_op:
        batch_op.drop_column('is_active')

    # ### end Alembic commands ###
