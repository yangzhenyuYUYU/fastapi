from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from typing import List
from middleware.auth import get_current_user
from models.user import User
from tools.oss import OSSClient
import time
import random
import os
import string
from urllib.parse import urlparse, unquote
import logging

router = APIRouter(prefix="/upload", tags=["文件上传"])
oss_client = OSSClient()
logger = logging.getLogger(__name__)

class FileType:
    """文件类型枚举"""
    DOCUMENT = "docs"     # 文档
    IMAGE = "images"      # 图片
    AUDIO = "audios"     # 音频
    VIDEO = "videos"     # 视频
    OTHER = "others"     # 其他

def get_file_type(filename: str, content_type: str = None) -> str:
    """根据文件名和Content-Type判断文件类型
    
    Args:
        filename: 文件名
        content_type: 文件的Content-Type
    
    Returns:
        str: 文件类型对应的文件夹名
    """
    # 获取文件扩展名
    ext = os.path.splitext(filename)[1].lower()
    
    # 文档类型
    document_types = {
        '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.pdf', '.txt', '.csv', '.rtf', '.odt'
    }
    
    # 图片类型
    image_types = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', 
        '.webp', '.svg', '.ico'
    }
    
    # 音频类型
    audio_types = {
        '.mp3', '.wav', '.ogg', '.m4a', '.aac',
        '.wma', '.flac', '.ape'
    }
    
    # 视频类型
    video_types = {
        '.mp4', '.avi', '.mov', '.wmv', '.flv',
        '.mkv', '.webm', '.m4v', '.mpg', '.mpeg'
    }
    
    # 根据扩展名判断类型
    if ext in document_types:
        return FileType.DOCUMENT
    elif ext in image_types:
        return FileType.IMAGE
    elif ext in audio_types:
        return FileType.AUDIO
    elif ext in video_types:
        return FileType.VIDEO
        
    # 如果有Content-Type，再次确认
    if content_type:
        if content_type.startswith('image/'):
            return FileType.IMAGE
        elif content_type.startswith('audio/'):
            return FileType.AUDIO
        elif content_type.startswith('video/'):
            return FileType.VIDEO
        elif content_type in ['application/pdf', 'application/msword',
                            'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
            return FileType.DOCUMENT
            
    return FileType.OTHER

def generate_unique_filename(user: User, ext: str) -> str:
    """生成唯一的文件名
    
    格式: P{phone}T{timestamp}R{random_code}{ext}
    P: Phone number marker
    T: Timestamp marker
    R: Random code marker
    
    Args:
        user: 用户
        ext: 文件扩展名
    
    Returns:
        str: 生成的文件名
    """
    timestamp = int(time.time() * 1000)  # 毫秒级时间戳
    random_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    if user.phone:
        return f"P{user.phone}T{timestamp}R{random_code}{ext}"
    else:
        return f"ID{user.id}T{timestamp}R{random_code}{ext}"

@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    folder: str = None,
    name: str = None,
    current_user: User = Depends(get_current_user)
):
    try:
        # 添加文件信息日志
        logger.info(f"Uploading file: {file.filename}")
        logger.info(f"Content-Type: {file.content_type}")
        
        # 获取文件扩展名
        ext = os.path.splitext(file.filename)[1].lower()
        
        # 如果未指定folder，根据文件类型自动判断
        if not folder:
            folder = get_file_type(file.filename, file.content_type)
            
        # 生成唯一文件名
        filename = generate_unique_filename(current_user, ext)
        full_path = f"{folder}/{filename}"
        
        # 读取文件内容
        content = await file.read()
        logger.debug(f"File size: {len(content)} bytes")
        
        # 上传到OSS
        if not oss_client.upload_file(full_path, content):
            raise HTTPException(status_code=400, detail="文件上传失败")
        
        # 获取永久公共访问URL
        file_url = oss_client.get_public_url(full_path)

        response_data = {
            "url": file_url,
            "filename": full_path,
            "type": folder
        }

        # 如果是音频文件,计算时长
        if folder == FileType.AUDIO:
            logger.info(f"Processing audio file: {file.filename}")
            duration = AudioUtils.get_duration(content)
            logger.info(f"Audio duration result: {duration}s")
            response_data["duration"] = duration

        return {
            "code": 0,
            "msg": "success",
            "data": response_data
        }
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/files")
async def upload_files(
    files: List[UploadFile] = File(...),
    folder: str = None,
    current_user: User = Depends(get_current_user)
):
    """批量上传文件"""
    try:
        result = []
        for file in files:
            # 获取文件扩展名
            ext = os.path.splitext(file.filename)[1].lower()
            
            # 如果未指定folder，根据文件类型自动判断
            file_folder = folder or get_file_type(file.filename, file.content_type)
            
            # 生成唯一文件名
            filename = generate_unique_filename(current_user.phone, ext)
            full_path = f"{file_folder}/{filename}"
            
            # 读取文件内容
            content = await file.read()
            
            # 上传到OSS
            if oss_client.upload_file(full_path, content):
                file_url = oss_client.get_public_url(full_path)
                file_data = {
                    "url": file_url,
                    "filename": full_path,
                    "type": file_folder,
                    "original_name": file.filename
                }
                
                # 如果是音频文件,计算时长
                if file_folder == FileType.AUDIO:
                    duration = AudioUtils.get_duration(content)
                    file_data["duration"] = duration
                    logger.info(f"Audio file processed: {file.filename}, duration: {duration}s")
                    
                result.append(file_data)
        
        return {
            "code": 0,
            "msg": "success",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/file")
async def delete_file(
    filename: str,
    current_user: User = Depends(get_current_user)
):
    """删除文件
    
    Args:
        filename: 文件名（包含路径）
    """
    try:
        logger.info(f"Original filename: {filename}")
        
        # 如果是完整的 URL，提取实际的文件路径
        if filename.startswith('http'):
            # 先进行 URL 解码（可能是多重编码）
            decoded_filename = unquote(unquote(filename))
            logger.info(f"Decoded filename: {decoded_filename}")
            
            # 移除查询参数
            if '?' in decoded_filename:
                decoded_filename = decoded_filename.split('?')[0]
            logger.info(f"After removing query params: {decoded_filename}")
            
            # 提取文件路径部分
            parsed_url = urlparse(decoded_filename)
            path = parsed_url.path.lstrip('/')
            logger.info(f"Extracted path: {path}")
            
            # 如果路径中包含 bucket 名称，移除它
            if '/' in path:
                filename = path.split('/', 1)[1]
            else:
                filename = path
        else:
            # 如果不是URL，也需要解码（处理可能的编码字符）
            filename = unquote(unquote(filename))
            if '?' in filename:
                filename = filename.split('?')[0]
        
        # 处理可能的URL编码斜杠
        filename = filename.replace('%2F', '/').replace('%2f', '/')
        logger.info(f"Final filename to delete: {filename}")

        # 直接尝试删除文件
        success = oss_client.delete_file(filename)
        
        if success:
            return {
                "code": 0,
                "msg": "success"
            }
        else:
            raise HTTPException(status_code=404, detail="文件删除失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
