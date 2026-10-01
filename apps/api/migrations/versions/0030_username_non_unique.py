"""username: display label instead of a unique key.

Usernames become non-unique display labels; user_id (UUID) is the
canonical identifier for users. The unique index on users.username
becomes a plain lookup index. Login no longer resolves by username
(it resolves by API key, see dashboard_auth), so duplicate usernames
create no ambiguity in authentication.

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-30
"""

from alembic import op

revision = "0030_username_non_unique"
down_revision = "0029_organizations"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_users_username"


def upgrade() -> None:
    # Drop the UNIQUE index, recreate it as a plain b-tree index: the
    # column stays indexed for prefix searches, but duplicate usernames
    # are now allowed.
    op.drop_index(INDEX_NAME, table_name="users")
    op.create_index(INDEX_NAME, "users", ["username"])


def downgrade() -> None:
    # Restoring the unique index fails when duplicate usernames exist;
    # that is intentional for a data-semantics change.
    op.drop_index(INDEX_NAME, table_name="users")
    op.create_index(INDEX_NAME, "users", ["username"], unique=True)
