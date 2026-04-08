import base64
import hashlib


def calculate_signature(
    timestamp: str,
    nonce: str,
    encrypt_key: str,
    body: bytes,
) -> str:
    payload = timestamp.encode("utf-8") + nonce.encode("utf-8") + encrypt_key.encode("utf-8") + body
    return hashlib.sha256(payload).hexdigest()


def decrypt_event(encrypt: str, encrypt_key: str) -> str:
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import padding
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Encrypted Feishu callbacks require the 'cryptography' package."
        ) from exc

    encrypted_bytes = base64.b64decode(encrypt)
    if len(encrypted_bytes) < 16:
        raise ValueError("Encrypted Feishu payload is too short.")
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    iv = encrypted_bytes[:16]
    ciphertext = encrypted_bytes[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode("utf-8")
