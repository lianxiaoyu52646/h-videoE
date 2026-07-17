"""
测试用 bilibili-api-python 绕过 verify 获取字幕
"""
import asyncio
from bilibili_api import video
from bilibili_api.utils.network import Api
from bilibili_api.video import API


async def test():
    v = video.Video(bvid='BV1z7411P7xb')
    info = await v.get_info()
    pages = info.get('pages', [])
    cid = pages[1]['cid']  # 第2P
    print(f'cid={cid}')

    # 直接用 Api 类，但把 verify 改为 False
    api = API["info"]["get_player_info"]
    # 复制 api 配置，但 verify 设为 False
    api_modified = {
        "url": api["url"],
        "method": api["method"],
        "verify": False,  # 绕过验证
        "wbi": api.get("wbi", False),
        "dm": api.get("dm", False),
        "data": api.get("data", {}),
        "comment": api.get("comment", ""),
    }

    params = {
        "aid": v.get_aid(),
        "cid": cid,
        "isGaiaAvoided": False,
        "web_location": 1315873,
    }

    result = await Api(**api_modified, credential=v.credential).update_params(**params).result
    subtitles = result.get("subtitle", {}).get("subtitles", [])
    print(f'subtitle count: {len(subtitles)}')
    for s in subtitles:
        print(f'  lan={s.get("lan")} lan_doc={s.get("lan_doc")} url={s.get("subtitle_url", "")[:80]}')


asyncio.run(test())
