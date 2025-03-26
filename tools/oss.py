import oss2
from itertools import islice
import time
import random
from typing import Optional, Union
from config.settings import Settings
from urllib.parse import urlparse, parse_qs, unquote, urlencode
import logging

settings = Settings()
logger = logging.getLogger(__name__)

class OSSConfig:
    """OSS配置类"""
    ACCESS_KEY_ID = settings.OSS_ACCESS_KEY_ID
    ACCESS_KEY_SECRET = settings.OSS_ACCESS_KEY_SECRET
    ENDPOINT = settings.OSS_ENDPOINT
    INTERNAL_ENDPOINT = settings.OSS_INTERNAL_ENDPOINT
    REGION = 'cn-hangzhou'
    DEFAULT_BUCKET = settings.OSS_BUCKET_NAME

class OSSClient:
    """阿里云OSS客户端封装类"""
    
    def __init__(
        self,
        access_key_id: str = OSSConfig.ACCESS_KEY_ID,
        access_key_secret: str = OSSConfig.ACCESS_KEY_SECRET,
        endpoint: str = OSSConfig.ENDPOINT,
        internal_endpoint: str = OSSConfig.INTERNAL_ENDPOINT,
        region: str = OSSConfig.REGION,
        bucket_name: str = OSSConfig.DEFAULT_BUCKET
    ):
        """初始化OSS客户端"""
        try:
            self.auth = oss2.Auth(access_key_id, access_key_secret)
            
            # 判断是否使用内网地址
            try:
                import requests
                metadata_url = "http://100.100.100.200/latest/meta-data/"
                requests.get(metadata_url, timeout=0.1)
                self.endpoint = internal_endpoint
            except:
                self.endpoint = endpoint
            self.region = region
            self.bucket_name = bucket_name
            
            # 创建 Bucket 实例
            self.bucket = oss2.Bucket(self.auth, self.endpoint, bucket_name)
            
            # 确保 bucket 存在并设置为公共读取
            self._ensure_bucket_exists()
            self.set_bucket_acl(oss2.BUCKET_ACL_PUBLIC_READ)
        except Exception as e:
            raise
    
    def _ensure_bucket_exists(self) -> None:
        """确保 bucket 存在，如果不存在则创建"""
        try:
            # 检查 bucket 是否存在
            try:
                self.bucket.get_bucket_info()
            except oss2.exceptions.NoSuchBucket:
                # 创建 bucket 并设置为公共读取
                self.bucket.create_bucket(oss2.BUCKET_ACL_PUBLIC_READ)
        except Exception as e:
            raise Exception(f"Failed to ensure bucket exists: {e}")
    
    @staticmethod
    def generate_unique_bucket_name(prefix: str = 'demo') -> str:
        """生成唯一的Bucket名称"""
        timestamp = int(time.time())
        random_number = random.randint(0, 9999)
        return f"{prefix}-{timestamp}-{random_number}"
    
    def create_bucket(self, acl: str = oss2.models.BUCKET_ACL_PRIVATE) -> bool:
        """创建Bucket"""
        try:
            self.bucket.create_bucket(acl)
            return True
        except oss2.exceptions.OssError as e:
            return False
    
    def upload_file(
        self,
        object_name: str,
        data: Union[str, bytes, bytearray],
        content_type: Optional[str] = None
    ) -> bool:
        """上传文件"""
        try:
            # 确保 bucket 存在
            self._ensure_bucket_exists()
            
            # 如果传入的是字符串，转换为bytes
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            headers = {}
            if content_type:
                headers['Content-Type'] = content_type
                
            result = self.bucket.put_object(object_name, data, headers=headers)
            return True
        except Exception as e:
            return False
    
    def download_file(self, object_name: str) -> Optional[str]:
        """下载文件"""
        try:
            file_obj = self.bucket.get_object(object_name)
            content = file_obj.read().decode('utf-8')
            return content
        except oss2.exceptions.OssError as e:
            return None
    
    def list_objects(self, max_objects: int = 10) -> list:
        """列出Bucket中的对象"""
        try:
            objects = list(islice(oss2.ObjectIterator(self.bucket), max_objects))
            return [obj.key for obj in objects]
        except oss2.exceptions.OssError as e:
            return []
    
    def delete_object(self, object_name: str) -> bool:
        """删除单个对象
        
        Args:
            object_name: 对象名称或完整URL
            
        Returns:
            bool: 是否删除成功
        """
        try:
            logger.info(f"Start deleting object: {object_name}")
            
            # 如果是完整URL，提取object_name
            if "http" in object_name or "https" in object_name:
                # 先进行URL解码
                object_name = unquote(object_name)
                logger.info(f"After URL decode: {object_name}")
                
                # 移除域名部分
                if '.com/' in object_name:
                    object_name = object_name.split('.com/')[-1]
                logger.info(f"After removing domain: {object_name}")
                
                # 移除签名参数
                if '?' in object_name:
                    object_name = object_name.split('?')[0]
                logger.info(f"After removing query params: {object_name}")
                
                # 再次URL解码(处理可能的双重编码)
                object_name = unquote(object_name)
                logger.info(f"Final object name: {object_name}")
            
            # 直接尝试删除文件
            try:
                self.bucket.delete_object(object_name)
                return True
            except oss2.exceptions.NoSuchKey:
                # 如果文件不存在也视为删除成功
                logger.info(f"Object not found (already deleted): {object_name}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete object {object_name}: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to delete object {object_name}: {str(e)}")
            return False
    
    def delete_all_objects(self, max_objects: int = 100) -> bool:
        """删除所有对象
        
        Args:
            max_objects: 最大删除数量
            
        Returns:
            bool: 是否全部删除成功
        """
        try:
            # 获取对象列表
            objects = self.list_objects(max_objects)
            if not objects:
                return True
            
            # 记录删除失败的对象
            failed_objects = []
            
            # 逐个删除并验证
            for object_name in objects:
                if not self.delete_object(object_name):
                    failed_objects.append(object_name)
                    logger.error(f"Failed to delete object: {object_name}")
            
            # 只有全部删除成功才返回True
            if failed_objects:
                logger.error(f"Some objects failed to delete: {failed_objects}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete all objects: {str(e)}")
            return False
    
    def delete_bucket(self) -> bool:
        """删除Bucket"""
        try:
            self.bucket.delete_bucket()
            return True
        except Exception as e:
            return False
    
    def get_signed_url(self, object_name: str, expires: int = 3600) -> str:
        """获取文件的签名 URL
        
        Args:
            object_name: OSS 对象名称
            expires: 过期时间（秒），默认1小时
            
        Returns:
            str: 签名 URL
        """
        try:
            # 如果是完整的 URL，提取对象名称
            if object_name.startswith('http'):
                object_name = object_name.split(f'{self.bucket_name}.{self.endpoint}/')[-1]
                if '?' in object_name:
                    object_name = object_name.split('?')[0]
                object_name = unquote(object_name)
            
            # 始终使用公网endpoint创建新的bucket实例来生成URL
            public_bucket = oss2.Bucket(self.auth, OSSConfig.ENDPOINT, self.bucket_name)
            url = public_bucket.sign_url('GET', object_name, expires)
            
            # 移除URL中的查询参数,保留签名必需的参数
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            essential_params = {
                'Expires': query_params.get('Expires', [None])[0],
                'OSSAccessKeyId': query_params.get('OSSAccessKeyId', [None])[0],
                'Signature': query_params.get('Signature', [None])[0]
            }
            
            # 重建URL,只包含必要参数
            essential_query = urlencode({k: v for k, v in essential_params.items() if v is not None})
            clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            if essential_query:
                clean_url = f"{clean_url}?{essential_query}"
                
            return clean_url
            
        except Exception as e:
            logger.error(f"Failed to get signed url: {str(e)}")
            return None
    
    def check_and_refresh_url(self, file_url: str, min_remaining_time: int = 300) -> str:
        """检查OSS URL是否即将过期，如果快过期则刷新
        
        Args:
            file_url: OSS文件的URL（带签名参数的完整URL）
            min_remaining_time: 最小剩余有效期（秒），默认5分钟
            
        Returns:
            str: 有效的签名URL
        """
        try:
            # 如果不是有效的URL，直接返回
            if not file_url or not file_url.startswith('http'):
                return file_url
            
            # 解析URL
            parsed_url = urlparse(file_url)
            query_params = parse_qs(parsed_url.query)
            
            # 提取过期时间
            expires = query_params.get('Expires', [None])[0]
            if not expires:
                # 如果URL中没有过期时间参数，生成新的签名URL
                object_name = self._extract_object_name(file_url)
                return self.get_signed_url(object_name)
            
            # 检查是否即将过期
            expires_timestamp = int(expires)
            current_time = int(time.time())
            remaining_time = expires_timestamp - current_time
            
            if remaining_time <= min_remaining_time:
                # 即将过期或已过期，生成新的签名URL
                object_name = self._extract_object_name(file_url)
                return self.get_signed_url(object_name)
            
            # 还未过期，返回清理后的URL
            essential_params = {
                'Expires': expires,
                'OSSAccessKeyId': query_params.get('OSSAccessKeyId', [None])[0],
                'Signature': query_params.get('Signature', [None])[0]
            }
            essential_query = urlencode({k: v for k, v in essential_params.items() if v is not None})
            clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
            if essential_query:
                clean_url = f"{clean_url}?{essential_query}"
                
            return clean_url
            
        except Exception as e:
            logger.error(f"Failed to check and refresh url: {str(e)}")
            return file_url
    
    def _extract_object_name(self, file_url: str) -> str:
        """从URL中提取object_name"""
        try:
            if "http" in file_url or "https" in file_url:
                # 移除协议和域名部分
                object_name = file_url.split('.com/')[-1]
                # 处理带签名参数的URL
                if '?' in object_name:
                    object_name = object_name.split('?')[0]
            else:
                object_name = file_url
            
            # URL解码
            return unquote(object_name)
        except Exception as e:
            return file_url
    
    def set_bucket_acl(self, acl: str = oss2.BUCKET_ACL_PUBLIC_READ) -> bool:
        """设置 Bucket 访问权限"""
        try:
            self.bucket.put_bucket_acl(acl)
            return True
        except Exception as e:
            return False
    
    def delete_file(self, object_name: str) -> bool:
        """从 OSS 删除文件
        
        Args:
            object_name: OSS 对象名称或完整URL
            
        Returns:
            bool: 是否删除成功
        """
        try:
            # 如果是完整的 URL，提取对象名称
            if object_name.startswith('http'):
                object_name = object_name.split(f'{self.bucket_name}.{self.endpoint}/')[-1]
                if '?' in object_name:
                    object_name = object_name.split('?')[0]
                object_name = unquote(object_name)
                
            # 调用delete_object方法,它会验证删除结果
            return self.delete_object(object_name)
            
        except Exception as e:
            logger.error(f"Failed to delete file {object_name}: {str(e)}")
            return False
    
    def get_public_url(self, object_name: str) -> str:
        """获取文件的永久公共访问URL（无需签名）
        
        Args:
            object_name: OSS对象名称
            
        Returns:
            str: 永久有效的公共访问URL
        """
        try:
            # 如果是完整URL，提取对象名称
            if object_name.startswith('http'):
                object_name = object_name.split(f'{self.bucket_name}.{self.endpoint}/')[-1]
                if '?' in object_name:
                    object_name = object_name.split('?')[0]
                object_name = unquote(object_name)
            
            # 构建永久公共访问URL
            return f"https://{self.bucket_name}.{OSSConfig.ENDPOINT}/{object_name}"
            
        except Exception as e:
            logger.error(f"Failed to get public url: {str(e)}")
            return None