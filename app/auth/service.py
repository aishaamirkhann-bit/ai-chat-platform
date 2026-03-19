import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class AuthService:
    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    def create_token(self, user_id: int, email: str) -> str:
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def verify_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token. Please login again.",
                headers={"WWW-Authenticate": "Bearer"},
            )


# Global instance
auth_service = AuthService()


# Standalone function — saare routers yeh import karte hain
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    return auth_service.verify_token(token)