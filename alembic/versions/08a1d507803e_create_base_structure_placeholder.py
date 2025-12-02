from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '08a1d507803e'
down_revision: Union[str, Sequence[str], None] = None  # <-- STARTING POINT
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all necessary core tables."""
    # Assuming standard table definitions based on previous migration attempts/names.

    # Core Table 1: healthcare_providers (Hospitals/Clinics)
    op.create_table('healthcare_providers',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=100), nullable=False),
                    sa.Column('address', sa.String(length=255), nullable=False),
                    sa.Column('city', sa.String(length=100), nullable=False),
                    sa.Column('service_type', sa.Enum('hospital', 'clinic', 'blood_bank', name='servicetypeenum'),
                              nullable=False),
                    sa.Column('is_active', sa.Boolean(), nullable=True),
                    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index(op.f('ix_healthcare_providers_id'), 'healthcare_providers', ['id'], unique=False)

    # Core Table 2: blood_donors
    op.create_table('blood_donors',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),  # Assuming FK to users table later
                    sa.Column('blood_type',
                              sa.Enum('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', name='bloodtypeenum'),
                              nullable=False),
                    sa.Column('last_donation_date', sa.Date(), nullable=True),
                    sa.Column('is_available', sa.Boolean(), nullable=True),
                    sa.Column('city', sa.String(length=100), nullable=False),
                    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
                    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index(op.f('ix_blood_donors_id'), 'blood_donors', ['id'], unique=False)

    # Core Table 3: blood_requests
    op.create_table('blood_requests',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('hospital_id', sa.Integer(), sa.ForeignKey('healthcare_providers.id'), nullable=False),
                    sa.Column('blood_type',
                              sa.Enum('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', name='bloodtypeenum'),
                              nullable=False),
                    sa.Column('needed_units', sa.Integer(), nullable=False),
                    sa.Column('city', sa.String(length=100), nullable=False),
                    sa.Column('urgent', sa.Boolean(), nullable=True),
                    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index(op.f('ix_blood_requests_id'), 'blood_requests', ['id'], unique=False)

    # Note: Other tables like 'users', 'transport_requests', 'healthcare_requests' etc.,
    # would need to be added here for a complete schema, but we'll focus on the tables
    # directly related to the existing migration chain for now.

    # If users table is not created here, the FK in blood_donors (user_id) will fail later.
    # Assuming a simple users table exists or will be created here:
    op.create_table('users',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('email', sa.String(), nullable=False, unique=True),
                    sa.Column('hashed_password', sa.String(), nullable=False),
                    sa.Column('is_active', sa.Boolean(), nullable=True),
                    sa.PrimaryKeyConstraint('id')
                    )
    # Re-apply FK to blood_donors now that users exists
    op.create_foreign_key(None, 'blood_donors', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('users')
    op.drop_table('blood_requests')
    op.drop_table('blood_donors')
    op.drop_table('healthcare_providers')
