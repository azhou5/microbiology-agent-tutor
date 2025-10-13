"""Startup script for MicroTutor V4 with HTTPS support.

This script supports both HTTP (localhost) and HTTPS (network access).
For HTTPS, it will auto-generate self-signed certificates if they don't exist.
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def generate_self_signed_cert(cert_dir: Path) -> tuple[str, str]:
    """Generate self-signed SSL certificate for local development.
    
    Args:
        cert_dir: Directory to store certificates
        
    Returns:
        Tuple of (cert_path, key_path)
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from datetime import datetime, timedelta
        import socket
    except ImportError:
        print("❌ cryptography package required for HTTPS support")
        print("   Install: pip install cryptography")
        sys.exit(1)
    
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_file = cert_dir / "cert.pem"
    key_file = cert_dir / "key.pem"
    
    if cert_file.exists() and key_file.exists():
        print(f"✅ Using existing certificates from {cert_dir}")
        return str(cert_file), str(key_file)
    
    print("🔐 Generating self-signed SSL certificate...")
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Get hostname and IP
    hostname = socket.gethostname()
    
    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Dev"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MicroTutor"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("*.localhost"),
                x509.DNSName(hostname),
                x509.IPAddress(__import__("ipaddress").IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    
    # Write certificate
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    # Write private key
    with open(key_file, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
    
    print(f"✅ Certificates generated in {cert_dir}")
    print("⚠️  Note: Browser will show security warning for self-signed certs")
    print("    Click 'Advanced' -> 'Proceed to localhost' to continue")
    
    return str(cert_file), str(key_file)


def get_local_ip() -> str:
    """Get the local IP address."""
    import socket
    
    try:
        # Connect to external server to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "Unable to determine"


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run MicroTutor V4 with optional HTTPS")
    parser.add_argument(
        "--https",
        action="store_true",
        help="Enable HTTPS (required for microphone access over network)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5001,
        help="Port to bind to (default: 5001)",
    )
    parser.add_argument(
        "--cert-dir",
        default="./ssl_certs",
        help="Directory for SSL certificates (default: ./ssl_certs)",
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 Starting MicroTutor V4 (FastAPI + Pydantic)")
    print("=" * 60)
    print()
    
    ssl_keyfile = None
    ssl_certfile = None
    protocol = "http"
    
    if args.https:
        cert_dir = Path(args.cert_dir)
        ssl_certfile, ssl_keyfile = generate_self_signed_cert(cert_dir)
        protocol = "https"
        print(f"🔒 HTTPS Mode: Enabled")
    else:
        print(f"🔓 HTTP Mode: Enabled (HTTPS with --https flag)")
    
    print()
    print("📡 Access URLs:")
    print(f"   Localhost:  {protocol}://localhost:{args.port}")
    print(f"   Network IP: {protocol}://{get_local_ip()}:{args.port}")
    print()
    print("📚 API Documentation:")
    print(f"   Swagger UI: {protocol}://localhost:{args.port}/api/docs")
    print(f"   ReDoc:      {protocol}://localhost:{args.port}/api/redoc")
    print()
    print("🎤 Microphone Access:")
    if args.https:
        print("   ✅ Available on all URLs (HTTPS enabled)")
    else:
        print("   ✅ Available on localhost/127.0.0.1")
        print("   ❌ NOT available on network IP (use --https for network access)")
    print()
    print("=" * 60)
    print()
    
    uvicorn.run(
        "microtutor.api.app:app",
        host=args.host,
        port=args.port,
        reload=True,
        log_level="info",
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
    )

