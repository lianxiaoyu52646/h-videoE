"""
Bilibili 扫码登录服务

功能：
1. 生成二维码（终端打印 + 返回二维码图片URL）
2. 轮询扫码状态
3. 登录成功后自动保存 Cookie 到 bilibili_config.json
4. 提供 Cookie 有效性检查
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import httpx
from sqlmodel import Session

from app import crud
from app import database

# Bilibili API 请求头
_BILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}

# Cookie 配置文件路径
_BILI_CONFIG_FILE = Path(__file__).parent.parent.parent / "bilibili_config.json"

# 扫码登录 API
_QRCODE_LOGIN_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
_QRCODE_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

# Cookie 有效性检查 API
_COOKIE_INFO_URL = "https://api.bilibili.com/x/web-interface/nav"


def _save_credential(cfg: dict, *, user_id: int | None = None, username: str | None = None):
    """保存凭证到数据库，并保留文件回退。"""
    _BILI_CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with Session(database.engine) as session:
        crud.save_platform_credential(
            session,
            "bilibili",
            cfg,
            username=username,
            user_id=user_id,
        )
    print(f"[bili_auth] credential saved to {_BILI_CONFIG_FILE}")


def load_credential(user_id: int | None = None) -> Optional[dict]:
    """优先从数据库加载，回退到 bilibili_config.json。"""
    with Session(database.engine) as session:
        row = crud.get_platform_credential(session, "bilibili", user_id=user_id)
        if row and row.credential_json.get("sessdata"):
            return row.credential_json
    if _BILI_CONFIG_FILE.exists():
        try:
            cfg = json.loads(_BILI_CONFIG_FILE.read_text(encoding="utf-8"))
            if cfg.get("sessdata"):
                return cfg
        except Exception:
            pass
    return None


def get_cookie_header(user_id: int | None = None) -> str:
    """构造 Cookie 请求头"""
    cfg = load_credential(user_id=user_id)
    if not cfg:
        return ""
    parts = []
    if cfg.get("sessdata"):
        parts.append(f"SESSDATA={cfg['sessdata']}")
    if cfg.get("bili_jct"):
        parts.append(f"BILI_JCT={cfg['bili_jct']}")
    if cfg.get("buvid3"):
        parts.append(f"buvid3={cfg['buvid3']}")
    if cfg.get("dedeuserid"):
        parts.append(f"DedeUserID={cfg['dedeuserid']}")
    return "; ".join(parts)


def get_api_credential(user_id: int | None = None):
    """构造 bilibili-api-python Credential（自动 WBI 签名）"""
    cfg = load_credential(user_id=user_id)
    if not cfg or not cfg.get("sessdata"):
        return None
    try:
        from bilibili_api import Credential
        return Credential(
            sessdata=cfg.get("sessdata"),
            bili_jct=cfg.get("bili_jct"),
            buvid3=cfg.get("buvid3"),
            dedeuserid=cfg.get("dedeuserid"),
        )
    except ImportError:
        return None


async def generate_qrcode() -> dict:
    """生成扫码登录二维码
    
    Returns:
        {
            "qrcode_url": str,       # 二维码内容URL
            "qrcode_key": str,       # 轮询用的 key
            "qrcode_image": str,     # base64 编码的二维码图片（data URI）
        }
    """
    async with httpx.AsyncClient(timeout=15, headers=_BILI_HEADERS) as client:
        resp = await client.get(_QRCODE_LOGIN_URL)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Failed to generate qrcode: {data.get('message')}")
        
        result = data["data"]
        qrcode_url = result["url"]
        qrcode_key = result["qrcode_key"]
        
        # 在后端生成二维码图片，返回 base64 data URI
        qrcode_image = _generate_qrcode_image(qrcode_url)
        
        return {
            "qrcode_url": qrcode_url,
            "qrcode_key": qrcode_key,
            "qrcode_image": qrcode_image,
        }


def _generate_qrcode_image(text: str) -> str:
    """用 qrcode 库生成二维码图片，返回 data URI（base64）"""
    try:
        import qrcode
        import io
        import base64
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except ImportError:
        print("[bili_auth] qrcode library not installed, returning URL only")
        return ""


async def poll_login_status(qrcode_key: str, user_id: int | None = None) -> dict:
    """轮询扫码登录状态
    
    Returns:
        {
            "status": str,       # "waiting" | "scanned" | "success" | "expired" | "error"
            "message": str,      # 状态描述
            "cookie": dict|null, # 登录成功时的 cookie 信息
        }
    """
    async with httpx.AsyncClient(timeout=15, headers=_BILI_HEADERS) as client:
        resp = await client.get(_QRCODE_POLL_URL, params={"qrcode_key": qrcode_key})
        data = resp.json()
        
        if data.get("code") != 0:
            return {"status": "error", "message": data.get("message", "未知错误"), "cookie": None}
        
        result = data["data"]
        code = result.get("code", -1)
        
        if code == 86090:
            # 已扫码，等待确认
            return {"status": "scanned", "message": "已扫码，请在手机上确认登录", "cookie": None}
        elif code == 86038:
            # 二维码已失效
            return {"status": "expired", "message": "二维码已过期，请重新生成", "cookie": None}
        elif code == 0:
            # 登录成功
            # 从响应的 url 中提取 cookie 参数
            redirect_url = result.get("url", "")
            cookie_str = result.get("cookie", "")
            
            # 解析 cookie
            cfg = _parse_cookie_from_response(redirect_url, resp)
            if cfg:
                _save_credential(cfg, user_id=user_id)
                return {
                    "status": "success",
                    "message": "登录成功！Cookie 已自动保存",
                    "cookie": cfg,
                }
            else:
                return {"status": "error", "message": "登录成功但解析 Cookie 失败", "cookie": None}
        else:
            # 仍在等待扫码
            return {"status": "waiting", "message": "等待扫码...", "cookie": None}


def _parse_cookie_from_response(redirect_url: str, resp: httpx.Response) -> Optional[dict]:
    """从登录成功的响应中解析 Cookie
    
    B站扫码登录成功后，Cookie 会通过 Set-Cookie 响应头返回，
    同时 redirect_url 中也包含 SESSDATA 等参数。
    """
    cfg = {}
    
    # 方法1: 从 Set-Cookie 响应头解析
    cookies = resp.cookies
    if cookies.get("SESSDATA"):
        cfg["sessdata"] = cookies.get("SESSDATA")
    if cookies.get("bili_jct"):
        cfg["bili_jct"] = cookies.get("bili_jct")
    if cookies.get("buvid3"):
        cfg["buvid3"] = cookies.get("buvid3")
    
    # 方法2: 从 redirect_url 的查询参数解析（备用）
    if not cfg.get("sessdata") and redirect_url:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)
        if "SESSDATA" in params:
            cfg["sessdata"] = params["SESSDATA"][0]
        if "bili_jct" in params:
            cfg["bili_jct"] = params["bili_jct"][0]
    
    # 方法3: 从 raw Set-Cookie headers 解析（最终兜底）
    if not cfg.get("sessdata"):
        for header_val in resp.headers.get_list("set-cookie"):
            if "SESSDATA=" in header_val:
                val = header_val.split("SESSDATA=")[1].split(";")[0]
                if val:
                    cfg["sessdata"] = val
            if "bili_jct=" in header_val:
                val = header_val.split("bili_jct=")[1].split(";")[0]
                if val:
                    cfg["bili_jct"] = val
            if "buvid3=" in header_val:
                val = header_val.split("buvid3=")[1].split(";")[0]
                if val:
                    cfg["buvid3"] = val
    
    return cfg if cfg.get("sessdata") else None


async def check_cookie_valid(user_id: int | None = None) -> dict:
    """检查当前 Cookie 是否有效
    
    Returns:
        {
            "valid": bool,
            "username": str|null,
            "is_login": bool,
            "message": str,
        }
    """
    cookie_header = get_cookie_header(user_id=user_id)
    if not cookie_header:
        return {"valid": False, "username": None, "is_login": False, "message": "未配置 Cookie"}
    
    headers = dict(_BILI_HEADERS)
    headers["Cookie"] = cookie_header
    
    async with httpx.AsyncClient(timeout=15, headers=headers) as client:
        resp = await client.get(_COOKIE_INFO_URL)
        data = resp.json()
        
        if data.get("code") != 0:
            return {"valid": False, "username": None, "is_login": False, "message": "Cookie 无效或已过期"}
        
        nav_data = data["data"]
        is_login = nav_data.get("isLogin", False)
        if is_login:
            username = nav_data.get("uname", "")
            mid = str(nav_data.get("mid", ""))
            # 同步保存 dedeuserid，提升字幕 API 成功率
            if mid:
                cfg = load_credential(user_id=user_id) or {}
                if cfg.get("dedeuserid") != mid:
                    cfg["dedeuserid"] = mid
                    _save_credential(cfg, user_id=user_id, username=username)
            return {"valid": True, "username": username, "is_login": True, "message": f"已登录: {username}"}
        else:
            return {"valid": False, "username": None, "is_login": False, "message": "Cookie 已过期，请重新扫码登录"}
