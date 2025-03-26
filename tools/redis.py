import redis
from config.settings import settings

class Redis:
    _client = None

    @classmethod
    def init(cls):
        """初始化Redis连接"""
        cls._client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True  # 自动解码响应
        )
    
    @classmethod
    def get(cls, key: str):
        """获取值"""
        if not cls._client:
            cls.init()
        return cls._client.get(key)
    
    @classmethod
    def set(cls, key: str, value: str, ex: int = None):
        """设置值"""
        if not cls._client:
            cls.init()
        return cls._client.set(key, value, ex=ex)
    
    @classmethod
    def delete(cls, key: str):
        """删除键"""
        if not cls._client:
            cls.init()
        return cls._client.delete(key)
    
    @classmethod
    def close(cls):
        """关闭连接"""
        if cls._client:
            cls._client.close()
            cls._client = None