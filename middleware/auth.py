from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from tools.jwt import JWTUtil
from models.user import User, UserSession, SessionStatus
from logging import getLogger

logger = getLogger(__name__)

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    获取当前用户的依赖函数
    用法：current_user: User = Depends(get_current_user)
    """
    token = credentials.credentials
    payload = JWTUtil.verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Token信息不完整",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 确保 user_id 是整数
    user_id = int(user_id)

    # 检查会话是否有效
    session = await UserSession.get_or_none(
        token=token,
        status=SessionStatus.ACTIVE
    )
    if not session:
        raise HTTPException(
            status_code=401,
            detail="您的账号已在其他地方上线, 请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 更新最后活跃时间(由于使用了auto_now,保存时会自动更新)
    await session.save()

    # 从数据库获取用户信息
    user = await User.get_or_none(id=user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user 


async def verify_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    验证用户是否是管理员
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="需要管理员权限",
        )
    return current_user
