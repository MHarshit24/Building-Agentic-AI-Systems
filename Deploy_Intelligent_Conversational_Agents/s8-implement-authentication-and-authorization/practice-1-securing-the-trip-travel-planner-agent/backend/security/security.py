# security.py
import os
from typing import Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import requests

from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[5]

env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

AUTH0_DOMAIN = os.getenv("VITE_AUTH0_DOMAIN") or os.getenv("AUTH0_DOMAIN")
API_AUDIENCE = os.getenv("VITE_AUTH0_AUDIENCE") or os.getenv("API_AUDIENCE")
ALGORITHMS = os.getenv("ALGORITHMS")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_jwks():
    url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    response = requests.get(url)
    return response.json()


def validate_token(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    try:
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)

        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key",
            )

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=[ALGORITHMS],
            audience=API_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/",
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )