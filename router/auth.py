from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from datetime import datetime, timedelta
from models.user import User
from config.settings import settings
from tools.format import format_response
from tools.jwt import JWTUtil

router = APIRouter(tags=["认证"])

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await User.get_or_none(username=form_data.username)
    if not user or user.password != form_data.password:  # 实际应该使用加密密码
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    access_token = JWTUtil.create_token({
        "sub": str(user.id),
        "username": user.username,
        "email": user.email,
        "credits": user.credits,
        "status": user.status,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    })
    
    return format_response(data={"access_token": access_token, "token_type": "bearer"}) 