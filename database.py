"""
database.py - Configuracion de Base de Datos MySQL
====================================================
Modulo de conexion y configuracion de la base de datos
usando SQLAlchemy con driver PyMySQL para XAMPP/MySQL.

Uso:
    from database import get_db, engine, Base
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv(Path(__file__).with_name(".env"))

# =============================================================================
# CONFIGURACION DE CONEXION
# =============================================================================

# URL de conexion: mysql+pymysql://usuario:password@host:puerto/base_datos
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost:3306/triaje_sistema")

# Crear engine con pool de conexiones
engine_options = {"pool_pre_ping": True, "pool_recycle": 3600}
if not DATABASE_URL.startswith("sqlite:"):
    engine_options.update(pool_size=10, max_overflow=20)
engine = create_engine(DATABASE_URL, **engine_options)

# Crear fabrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos SQLAlchemy
Base = declarative_base()


# =============================================================================
# DEPENDENCIA PARA FASTAPI
# =============================================================================

def get_db():
    """
    Generador de sesiones de base de datos para FastAPI.
    
    Uso en endpoints:
        @app.get("/endpoint")
        def mi_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def init_db():
    """Inicializa la base de datos creando todas las tablas definidas."""
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """Elimina todas las tablas (usar con cuidado en produccion)."""
    Base.metadata.drop_all(bind=engine)


def get_engine():
    """Retorna el engine de SQLAlchemy."""
    return engine
