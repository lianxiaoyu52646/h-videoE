import asyncio
from bilibili_api import video

async def test():
    v = video.Video(bvid='BV1z7411P7xb')
    info = await v.get_info()
    pages = info.get('pages', [])
    print('pages:', [(p['page'], p['cid'], p['part']) for p in pages[:5]])
    
    # 第2P (S01E02 First Food)
    cid = pages[1]['cid']
    print(f'\nFetching subtitles for cid={cid}...')
    sub = await v.get_subtitle(cid=cid)
    print('subtitle result type:', type(sub))
    print('subtitle result:', sub)

asyncio.run(test())
