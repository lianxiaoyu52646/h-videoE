"""
Bilibili 扫码登录 API 路由

提供以下接口：
- GET  /api/bili/login/qrcode  → 生成二维码
- GET  /api/bili/login/poll    → 轮询登录状态
- GET  /api/bili/login/status  → 检查 Cookie 有效性
"""
from fastapi import APIRouter
from app.services import bilibili_auth

router = APIRouter(prefix="/api/bili", tags=["bilibili-auth"])


@router.get("/login/qrcode")
async def generate_qrcode():
    """生成扫码登录二维码
    
    返回 qrcode_url（二维码内容URL），前端用此URL生成二维码图片。
    同时返回 qrcode_key，用于后续轮询登录状态。
    """
    try:
        result = await bilibili_auth.generate_qrcode()
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/login/poll")
async def poll_login(qrcode_key: str):
    """轮询扫码登录状态
    
    前端每 2 秒调用一次，传入 qrcode_key。
    返回 status: waiting | scanned | success | expired | error
    """
    result = await bilibili_auth.poll_login_status(qrcode_key)
    return result


@router.get("/login/status")
async def check_login_status():
    """检查当前 Cookie 是否有效
    
    返回 valid (bool) 和 username (str|null)。
    """
    result = await bilibili_auth.check_cookie_valid()
    return result
