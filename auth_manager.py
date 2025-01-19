import os
import logging
import json
import traceback
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from jose import JWTError, jwt
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

    def get_password_hash(self, password: str) -> str:
        """تشفير كلمة المرور"""
        # تحويل كلمة المرور إلى bytes وتشفيرها
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """التحقق من كلمة المرور مع تسجيل تفصيلي للأخطاء"""
        try:
            logger.info("بدء التحقق من كلمة المرور")
            logger.debug(f"طول كلمة المرور: {len(plain_password)}")
            logger.debug(f"طول كلمة المرور المشفرة: {len(hashed_password)}")
            
            # تحويل كلمة المرور إلى bytes
            plain_password_bytes = plain_password.encode('utf-8')
            hashed_password_bytes = hashed_password.encode('utf-8')
            
            # التحقق باستخدام bcrypt مباشرة
            is_valid = bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)
            
            logger.info(f"نتيجة التحقق من كلمة المرور: {is_valid}")
            
            # إذا كان التحقق فاشلًا، سنقوم بطباعة المزيد من المعلومات التفصيلية
            if not is_valid:
                logger.warning("معلومات إضافية للتصحيح:")
                logger.warning(f"طول كلمة المرور الأصلية: {len(plain_password)}")
                logger.warning(f"طول كلمة المرور المشفرة: {len(hashed_password)}")
            
            return is_valid
        except Exception as e:
            # تسجيل أي خطأ يحدث أثناء التحقق
            logger.error(f"خطأ في التحقق من كلمة المرور: {str(e)}")
            logger.error(f"التفاصيل الكاملة للخطأ: {traceback.format_exc()}")
            return False

    async def get_user(self, username: str) -> Optional[UserInDB]:
        """استرجاع معلومات المستخدم مع التعامل مع الأخطاء"""
        try:
            # الحصول على العميل الحالي
            clients = await self.redis_manager.get_current_clients()
            redis_client = clients['text']

            logger.info(f"محاولة استرجاع المستخدم: {username}")

            # البحث عن المستخدم
            user_data = await redis_client.hgetall(f"user:{username}")
            
            logger.info("بيانات المستخدم التفصيلية:")
            for key, value in user_data.items():
                logger.info(f"{key}: {value}")

            # التحقق من وجود المستخدم
            if not user_data:
                logger.warning(f"لم يتم العثور على المستخدم: {username}")
                return None

            # معالجة نطاقات الصلاحيات بشكل أكثر مرونة
            scopes_str = user_data.get('scopes', '[]')
            try:
                # محاولة تحويل النطاقات من JSON
                scopes = json.loads(scopes_str) if scopes_str else []
            except (json.JSONDecodeError, TypeError):
                # استخدام النص مباشرة إذا فشل التحويل
                scopes = [scopes_str] if scopes_str else []

            # التحقق من وجود كلمة المرور المشفرة
            hashed_password = user_data.get('hashed_password', '')
            if not hashed_password:
                logger.error(f"لا توجد كلمة مرور مشفرة للمستخدم: {username}")
                return None

            # إنشاء كائن المستخدم
            user = UserInDB(
                username=username,
                hashed_password=hashed_password,
                scopes=scopes,
                disabled=bool(int(user_data.get('disabled', '0')))
            )

            logger.info("تم استرجاع المستخدم بنجاح")
            return user

        except Exception as e:
            # تسجيل أي أخطاء تحدث أثناء استرجاع المستخدم
            logger.error(f"خطأ في استرجاع بيانات المستخدم {username}: {str(e)}")
            logger.error(f"التفاصيل الكاملة للخطأ: {traceback.format_exc()}")
            return None

    async def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        """مصادقة المستخدم مع التعامل الكامل مع الأخطاء"""
        try:
            # تسجيل محاولة المصادقة
            logger.info(f"محاولة مصادقة المستخدم: {username}")

            # استرجاع المستخدم
            user = await self.get_user(username)
            
            # التحقق من وجود المستخدم
            if not user:
                logger.warning(f"المستخدم غير موجود: {username}")
                return None

            # التحقق من تعطيل الحساب
            if user.disabled:
                logger.warning(f"الحساب معطل: {username}")
                raise AuthenticationError("الحساب معطل")

            # التحقق من كلمة المرور
            is_valid = await self.verify_password(password, user.hashed_password)
            
            # التعامل مع نتيجة التحقق
            if not is_valid:
                logger.warning(f"فشل التحقق من كلمة المرور للمستخدم: {username}")
                return None

            logger.info(f"تمت المصادقة بنجاح للمستخدم: {username}")
            return user

        except AuthenticationError as ae:
            # معالجة أخطاء المصادقة المحددة
            logger.error(f"خطأ في المصادقة: {str(ae)}")
            raise
        except Exception as e:
            # معالجة الأخطاء غير المتوقعة
            logger.error(f"خطأ غير متوقع في المصادقة: {str(e)}")
            logger.error(f"التفاصيل الكاملة للخطأ: {traceback.format_exc()}")
            return None

    # باقي الدوال تبقى كما هي دون تغيير
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