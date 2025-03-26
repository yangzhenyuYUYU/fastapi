from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise
from config.settings import TORTOISE_ORM
from router import (
    auth, 
    user, 
    # upload, 
    card, 
    trade, 
    wx
)

app = FastAPI(
    title="FastAPI Demo",
    description="FastAPI项目模板",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api")
app.include_router(user.router, prefix="/api")
# app.include_router(upload.router, prefix="/api")
app.include_router(card.router, prefix="/api")
app.include_router(trade.router, prefix="/api")
app.include_router(wx.router, prefix="/api")


# 注册数据库，修改setting.py文件相关配置后，方可解开使用
# register_tortoise(
#     app,
#     config=TORTOISE_ORM,
#     generate_schemas=True,
#     add_exception_handlers=True,
# )

# 启动命令：
# uvicorn main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 