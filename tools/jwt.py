from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from config.settings import Settings

settings = Settings()

class JWTUtil:
    # 密钥，建议放在环境变量中
    SECRET_KEY = settings.SECRET_KEY    
    ALGORITHM = settings.ALGORITHM
    ACCESS_TOKEN_EXPIRE_SECONDS = settings.ACCESS_TOKEN_EXPIRE_SECONDS

    @classmethod
    def create_token(self, data: dict) -> str:
        """创建token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(seconds=self.ACCESS_TOKEN_EXPIRE_SECONDS)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    @classmethod
    def verify_token(self, token: str) -> Optional[dict]:
        """验证token"""
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload
        except JWTError:
            return None