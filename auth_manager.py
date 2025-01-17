import os
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from redis_manager import EnhancedRedisManager
from custom_exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class Token(BaseModel):
    """نموذج التوكن"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInDB(BaseModel):
    """نموذج المستخدم في قاعدة البيانات"""
    username: str
    hashed_password: str
    scopes: List[str] = []
    disabled: bool = False


class AuthConfig:
    """تكوينات المصادقة"""
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))


class AuthManager:
    """مدير المصادقة والأمان"""

    def __init__(self, redis_manager: EnhancedRedisManager):
        """تهيئة مدير المصادقة"""
        if not redis_manager or not redis_manager.instances:
            raise ValueError("Redis manager with active connections is required")

        self.redis_manager = redis_manager
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """التحقق من كلمة المرور"""
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """تشفير كلمة المرور"""
        return self.pwd_context.hash(password)

    async def get_user(self, username: str) -> Optional[UserInDB]:
        """استرجاع معلومات المستخدم"""
        try:
            clients = await self.redis_manager.get_current_clients()
            redis_client = clients['text']

            user_data = await redis_client.hgetall(f"user:{username}")
            if not user_data:
                return None

            return UserInDB(
                username=username,
                hashed_password=user_data.get('hashed_password'),
                scopes=json.loads(user_data.get('scopes', '[]')),
                disabled=bool(int(user_data.get('disabled', '0')))
            )

        except Exception as e:
            logger.error(f"Error retrieving user data: {str(e)}")
            return None

    async def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """مصادقة المستخدم"""
        user = await self.get_user(username)
        if not user:
            return None
        if not await self.verify_password(password, user.hashed_password):
            return None
        if user.disabled:
            raise AuthenticationError("User account is disabled")
        return user

    async def create_tokens(self, user: UserInDB) -> Token:
        """إنشاء التوكن"""
        access_token_expires = timedelta(minutes=AuthConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = await self.create_access_token(
            data={"sub": user.username, "scopes": user.scopes},
            expires_delta=access_token_expires
        )

        refresh_token_expires = timedelta(days=AuthConfig.REFRESH_TOKEN_EXPIRE_DAYS)
        refresh_token = await self.create_refresh_token(
            data={"sub": user.username},
            expires_delta=refresh_token_expires
        )

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=AuthConfig.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    async def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """إنشاء توكن الوصول"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)

        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(
            to_encode,
            AuthConfig.SECRET_KEY,
            algorithm=AuthConfig.ALGORITHM
        )
        return encoded_jwt

    async def create_refresh_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """إنشاء توكن التحديث"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=7)

        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(
            to_encode,
            AuthConfig.SECRET_KEY,
            algorithm=AuthConfig.ALGORITHM
        )
        return encoded_jwt

    async def validate_token(self, token: str, token_type: str = "access") -> dict:
        """التحقق من صحة التوكن"""
        try:
            payload = jwt.decode(
                token,
                AuthConfig.SECRET_KEY,
                algorithms=[AuthConfig.ALGORITHM]
            )
            if payload.get("type") != token_type:
                raise AuthenticationError("Invalid token type")
            return payload
        except JWTError:
            raise AuthenticationError("Invalid token")