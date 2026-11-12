"""Create local administrator credentials once, without printing secrets."""
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from knowledge_access import password_hash


def main():
    root = Path(__file__).parent
    load_dotenv(root / '.env')
    if os.getenv('TRIAGE_ADMIN_PASSWORD_HASH'):
        print('El acceso del administrador ya está configurado.')
        return
    password = secrets.token_urlsafe(18)
    with (root / '.env').open('a', encoding='utf-8') as stream:
        stream.write('\nTRIAGE_ADMIN_USER=administrador\nTRIAGE_ADMIN_PASSWORD_HASH=' + password_hash(password) + '\n')
    (root / 'acceso-local.txt').write_text(
        'Administración del conocimiento\nUsuario: administrador\nClave: ' + password +
        '\nAbrir http://localhost:8000/conocimiento\nMantenga este archivo privado. No subir a GitHub.\n', encoding='utf-8')
    print('Acceso configurado. Credenciales en acceso-local.txt, excluido de Git.')


if __name__ == '__main__':
    main()
