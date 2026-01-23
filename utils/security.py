import os
import json
import base64
from cryptography.fernet import Fernet

KEY_FILE = ".secret.key"

def load_or_create_key():
    """
    Loads key from file or creates a new one.
    """
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        return key

def get_fernet():
    key = load_or_create_key()
    return Fernet(key)

def encrypt_dict(data: dict) -> str:
    """
    Encrypts a dictionary (converts to JSON string first).
    Returns token string.
    """
    f = get_fernet()
    json_str = json.dumps(data, ensure_ascii=False)
    token = f.encrypt(json_str.encode('utf-8'))
    return token.decode('utf-8')

def decrypt_dict(token: str) -> dict:
    """
    Decrypts token string back to dictionary.
    """
    f = get_fernet()
    json_bytes = f.decrypt(token.encode('utf-8'))
    return json.loads(json_bytes.decode('utf-8'))

def is_encrypted(data) -> bool:
    """
    Checks if data looks like an encrypted token (string).
    """
    if not isinstance(data, str):
        return False
    # Fernet tokens usually start with gAAAA
    return data.startswith("gAAAA")
