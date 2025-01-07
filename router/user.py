from fastapi import APIRouter, Depends
from models.user import User
from middleware.auth import get_current_user
from tools.format import format_response

router = APIRouter(prefix="/users", tags=["用户"])

@router.get("/me")
async def get_user_info(current_user: User = Depends(get_current_user)):
    return format_response(data={
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email
    })

@router.post("/")
async def create_user(username: str, password: str, email: str = None):
    user = await User.create(
        username=username,
        password=password,  # 实际应该加密存储
        email=email
    )
    return format_response(data={"id": user.id, "username": user.username}) 