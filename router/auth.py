from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from datetime import datetime, timedelta
from models.user import User
from config.setting import settings
from tools.format import format_response

router = APIRouter(tags=["认证"])

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await User.get_or_none(username=form_data.username)
    if not user or user.password != form_data.password:  # 实际应该使用加密密码
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = jwt.encode(
        claims={
            "sub": str(user.id),
            "exp": datetime.utcnow() + access_token_expires
        },
        key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return format_response(data={"access_token": access_token, "token_type": "bearer"}) 