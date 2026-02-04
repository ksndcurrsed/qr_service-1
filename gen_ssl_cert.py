"""Генерация самоподписанного SSL сертификата. Без ACME, без внешних сервисов."""
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import datetime
import os

# Домен для сертификата
DOMAIN = "fffzar-tool.ru"
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Local"),
        x509.NameAttribute(NameOID.COMMON_NAME, DOMAIN),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(DOMAIN)]),
        critical=False,
    ).sign(key, hashes.SHA256(), default_backend())
    
    cert_file = os.path.join(OUT_DIR, "cert.pem")
    key_file = os.path.join(OUT_DIR, "key.pem")
    
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    with open(key_file, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    print(f"Сертификат: {cert_file}")
    print(f"Ключ:       {key_file}")
    print()
    print("Запуск сервера:")
    print(f'  $env:SSL_CERTFILE = "{cert_file}"')
    print(f'  $env:SSL_KEYFILE = "{key_file}"')
    print("  python server.py")

if __name__ == "__main__":
    main()
