"""
init_db.py - Script de Inicializacion de Base de Datos
=======================================================
Ejecuta este script una sola vez para crear todas las tablas
en la base de datos triaje_sistema de MySQL/XAMPP.

Uso:
    python init_db.py
    
Verificar en phpMyAdmin: http://localhost/phpmyadmin
"""

import sys
from database import engine, Base, init_db
from models_db import (
    Paciente, EvaluacionTriaje, SignosVitalesHistorial,
    AlertaGenerada, DiagnosticoSugerido, ReglaConocimiento,
    SesionUsuario, EstadisticaDiaria
)


def main():
    print("=" * 60)
    print("  INICIALIZACION DE BASE DE DATOS - TRIAJE SISTEMA")
    print("=" * 60)
    print()
    
    print("[1] Conectando a MySQL en localhost:3306...")
    try:
        conn = engine.connect()
        print("     [OK] Conexion exitosa")
        conn.close()
    except Exception as e:
        print(f"     [ERROR] No se pudo conectar: {e}")
        print("     Verifica que XAMPP este corriendo con MySQL activado")
        sys.exit(1)
    
    print()
    print("[2] Creando tablas en 'triaje_sistema'...")
    init_db()
    
    print()
    print("[3] Tablas creadas:")
    tablas = Base.metadata.tables.keys()
    for tabla in sorted(tablas):
        print(f"     - {tabla}")
    
    print()
    print("[4] Verificando conexion final...")
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'triaje_sistema'"))
        count = result.scalar()
        print(f"     [OK] {count} tablas en la base de datos")
    
    print()
    print("=" * 60)
    print("  BASE DE DATOS INICIALIZADA CORRECTAMENTE")
    print("=" * 60)
    print()
    print("  Siguiente paso: ejecutar el servidor")
    print("  python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    print()
    print("  Verificar en phpMyAdmin: http://localhost/phpmyadmin")
    print("  Seleccionar base de datos: triaje_sistema")
    print()


if __name__ == "__main__":
    main()
