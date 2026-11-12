"""Local administrator session; operators cannot publish knowledge."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(tags=["Acceso al conocimiento"])
attempts = defaultdict(list)


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()
    return f'600000${salt}${digest}'


def check_password(password, encoded):
    try:
        iterations, salt, expected = encoded.split('$')
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def signing_key():
    return os.getenv('TRIAGE_ADMIN_PASSWORD_HASH', '').encode()


def usuario_actual(request: Request):
    try:
        payload, signature = request.cookies.get('triaje_admin', '').split('.')
        expected = hmac.new(signing_key(), payload.encode(), hashlib.sha256).hexdigest()
        if not signing_key() or not hmac.compare_digest(signature, expected):
            raise ValueError()
        claims = json.loads(base64.urlsafe_b64decode(payload))
        if claims['exp'] < time.time():
            raise ValueError()
        return {'usuario': claims['usuario'], 'rol': 'administrador'}
    except (ValueError, KeyError, TypeError):
        return {'usuario': None, 'rol': 'operador'}


def exigir_administrador(request):
    user = usuario_actual(request)
    if user['rol'] != 'administrador':
        raise HTTPException(401, 'Inicie sesión como administrador del conocimiento.')
    return user


class Login(BaseModel):
    usuario: str = Field(max_length=100)
    clave: str = Field(min_length=1, max_length=200)


@router.get('/conocimiento/sesion')
def session(request: Request):
    return usuario_actual(request)


@router.post('/conocimiento/sesion')
def login(data: Login, request: Request, response: Response):
    from symptom_extensions import validar_origen_local
    validar_origen_local(request)
    host = request.client.host
    now = time.monotonic()
    attempts[host] = [t for t in attempts[host] if now - t < 300]
    if len(attempts[host]) >= 5:
        raise HTTPException(429, 'Demasiados intentos. Espere cinco minutos.')
    configured = os.getenv('TRIAGE_ADMIN_USER', 'administrador')
    if data.usuario != configured or not check_password(data.clave, os.getenv('TRIAGE_ADMIN_PASSWORD_HASH', '')):
        attempts[host].append(now)
        raise HTTPException(401, 'Usuario o clave no válidos.')
    attempts.pop(host, None)
    payload = base64.urlsafe_b64encode(json.dumps({'usuario': configured, 'exp': time.time() + 28800,
                                                 'nonce': secrets.token_hex(16)}).encode()).decode()
    signature = hmac.new(signing_key(), payload.encode(), hashlib.sha256).hexdigest()
    response.set_cookie('triaje_admin', payload + '.' + signature, httponly=True, samesite='strict',
                        secure=request.url.scheme == 'https', max_age=28800)
    response.headers['Cache-Control'] = 'no-store'
    return {'usuario': configured, 'rol': 'administrador'}


@router.delete('/conocimiento/sesion')
def logout(request: Request, response: Response):
    from symptom_extensions import validar_origen_local
    validar_origen_local(request)
    response.delete_cookie('triaje_admin')
    return {'rol': 'operador'}
