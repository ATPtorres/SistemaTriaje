"""Additive, recorded schema upgrades. Never drop patient tables."""
from sqlalchemy import Column, DateTime, MetaData, String, Table, select
from datetime import datetime, timezone


def upgrade(engine):
    import models_db  # Register the current table definitions.
    from database import Base
    metadata = MetaData()
    versions = Table('schema_migrations', metadata,
                     Column('version', String(50), primary_key=True),
                     Column('aplicada_en', DateTime, nullable=False))
    metadata.create_all(engine)
    with engine.connect() as connection:
        installed = set(connection.execute(select(versions.c.version)).scalars())
    if '4.2.0-additive' not in installed:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(versions.insert().values(version='4.2.0-additive',
                                                         aplicada_en=datetime.now(timezone.utc)))
