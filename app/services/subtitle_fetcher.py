"""
视频 URL 解析 + 字幕抓取服务
支持: YouTube (yt-dlp 自动字幕), Bilibili (bilibili-api-python + Credential)
回退: faster-whisper ASR 语音识别

参考: https://github.com/dalitoytos-dotcom/bilibili-subtitle-fetcher
"""
import asyncio
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx

# Bilibili API 请求头
_BILI_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}

# Bilibili Cookie 配置文件
_BILI_CONFIG_FILE = Path(__file__).parent.parent.parent / "bilibili_config.json"


def _load_bili_credential(user_id: int | None = None):
    """加载 Bilibili 登录凭证（SESSDATA / BILI_JCT / BUVID3）
    
    优先使用 bilibili_auth 模块（支持扫码登录自动保存），
    回退到直接读取 bilibili_config.json
    """
    # 优先使用 bilibili_auth 模块
    try:
        from app.services import bilibili_auth
        cfg = bilibili_auth.load_credential(user_id=user_id)
        if cfg:
            return cfg
    except ImportError:
        pass
    
    # 回退：直接读取配置文件
    if _BILI_CONFIG_FILE.exists():
        try:
            cfg = json.loads(_BILI_CONFIG_FILE.read_text(encoding="utf-8"))
            if cfg.get("sessdata"):
                return cfg
        except Exception:
            pass
    return None


def _get_bili_cookie_header(user_id: int | None = None):
    """构造 Cookie 请求头"""
    # 优先使用 bilibili_auth 模块
    try:
        from app.services import bilibili_auth
        cookie = bilibili_auth.get_cookie_header(user_id=user_id)
        if cookie:
            return cookie
    except ImportError:
        pass
    
    # 回退：直接构造
    cfg = _load_bili_credential(user_id=user_id)
    if not cfg:
        return ""
    parts = []
    if cfg.get("sessdata"):
        parts.append(f"SESSDATA={cfg['sessdata']}")
    if cfg.get("bili_jct"):
        parts.append(f"BILI_JCT={cfg['bili_jct']}")
    if cfg.get("buvid3"):
        parts.append(f"buvid3={cfg['buvid3']}")
    return "; ".join(parts)


# ── URL 解析 ────────────────────────────────────────────
def parse_video_url(url: str) -> dict:
    """解析视频 URL，返回 source / video_id / embed_url / title / thumbnail"""
    if "youtube.com" in url or "youtu.be" in url:
        return _parse_youtube(url)
    if "bilibili.com" in url:
        return _parse_bilibili(url)
    return {"source": "generic", "video_id": None, "embed_url": None, "title": None, "thumbnail": None}


def _parse_youtube(url: str) -> dict:
    video_id = None
    patterns = [
        r"(?:youtube\.com/watch\?v=)([\w-]+)",
        r"(?:youtu\.be/)([\w-]+)",
        r"(?:youtube\.com/embed/)([\w-]+)",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            video_id = m.group(1)
            break
    return {
        "source": "youtube",
        "video_id": video_id,
        "embed_url": f"https://www.youtube.com/embed/{video_id}?enablejsapi=1&playsinline=1" if video_id else None,
        "title": None,
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else None,
    }


def _parse_bilibili(url: str) -> dict:
    m = re.search(r"/video/(BV[\w]+)", url, re.I)
    bvid = m.group(1) if m else None
    p_match = re.search(r"[?&]p=(\d+)", url)
    page = int(p_match.group(1)) if p_match else 1
    embed_url = f"https://player.bilibili.com/player.html?bvid={bvid}&high_quality=1&page={page}&danmaku=0&autoplay=0" if bvid else None
    return {
        "source": "bilibili",
        "video_id": bvid,
        "embed_url": embed_url,
        "title": None,
        "thumbnail": None,
    }


async def fetch_bilibili_title(bvid: str, user_id: int | None = None) -> Optional[str]:
    try:
        from bilibili_api import video as bili_video
        from app.services import bilibili_auth
        credential = bilibili_auth.get_api_credential(user_id=user_id)
        v = bili_video.Video(bvid=bvid, credential=credential)
        info = await v.get_info()
        return info.get("title")
    except Exception:
        return None


# ── 字幕抓取 ────────────────────────────────────────────
async def fetch_subtitles(
    url: str,
    source: str,
    on_batch=None,
    allow_whisper: bool = False,
    user_id: int | None = None,
) -> list[dict]:
    """抓取 CC/AI 字幕。默认不跑 Whisper，请用 fetch_subtitles_whisper。"""
    if source == "youtube":
        return await _fetch_youtube_subtitles(url, on_batch=on_batch, allow_whisper=allow_whisper)
    elif source == "bilibili":
        return await _fetch_bilibili_subtitles(
            url,
            on_batch=on_batch,
            allow_whisper=allow_whisper,
            user_id=user_id,
        )
    return []


async def fetch_subtitles_whisper(
    url: str,
    source: str,
    on_batch=None,
    user_id: int | None = None,
) -> list[dict]:
    """手动触发 Whisper 语音识别（慢，仅备选）。"""
    return await _whisper_fallback(url, source, on_batch=on_batch, user_id=user_id)


async def fetch_video_duration(url: str, source: str, user_id: int | None = None) -> float:
    """获取视频时长（秒）"""
    try:
        if source == "bilibili":
            m = re.search(r"/video/(BV[\w]+)", url, re.I)
            if not m:
                return 0
            from bilibili_api import video as bili_video
            from app.services import bilibili_auth
            cred = bilibili_auth.get_api_credential(user_id=user_id)
            v = bili_video.Video(bvid=m.group(1), credential=cred)
            info = await v.get_info()
            p_match = re.search(r"[?&]p=(\d+)", url)
            page = int(p_match.group(1)) if p_match else 1
            for p in info.get("pages", []):
                if p.get("page") == page:
                    return float(p.get("duration", 0))
            return float(info.get("duration", 0))
        if source == "youtube":
            import yt_dlp
            def _dur():
                with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    return float(info.get("duration") or 0)
            return await asyncio.to_thread(_dur)
    except Exception as e:
        print(f"[subtitle] duration fetch failed: {e}")
    return 0


# ── YouTube 字幕 (yt-dlp) ─────────────────────────────
async def _fetch_youtube_subtitles(url: str, on_batch=None, allow_whisper: bool = True) -> list[dict]:
    """用 yt-dlp 抓取 YouTube 自动字幕"""
    try:
        result = await asyncio.to_thread(_yt_dlp_subtitles, url)
        if result:
            return result
    except Exception as e:
        print(f"[subtitle] yt-dlp failed: {e}")
    if allow_whisper:
        return await _whisper_fallback(url, "youtube", on_batch=on_batch)
    return []


def _yt_dlp_subtitles(url: str) -> list[dict]:
    import yt_dlp
    ydl_opts = {
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "json3",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        subs = info.get("subtitles", {}) or info.get("automatic_captions", {})
        if not subs:
            return []
        for lang in ["en", "en-US", "en-GB"]:
            if lang in subs:
                for fmt in subs[lang]:
                    if fmt.get("ext") == "json3":
                        return _parse_json3_subtitle(fmt["url"])
        for lang_subs in subs.values():
            for fmt in lang_subs:
                if fmt.get("ext") in ("json3", "vtt", "srt"):
                    return _fetch_and_parse_subtitle(fmt["url"], fmt["ext"])
    return []


def _parse_json3_subtitle(url: str) -> list[dict]:
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    data = resp.json()
    segments = []
    for event in data.get("events", []):
        if "segs" not in event:
            continue
        text = "".join(seg.get("utf8", "") for seg in event["segs"]).strip()
        if not text:
            continue
        start = event.get("tStartMs", 0) / 1000.0
        duration = event.get("dDurationMs", 0) / 1000.0
        segments.append({"start": start, "end": start + duration, "text": text})
    return segments


def _fetch_and_parse_subtitle(url: str, fmt: str) -> list[dict]:
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    if fmt == "vtt":
        return _parse_vtt(resp.text)
    elif fmt == "srt":
        return _parse_srt(resp.text)
    return []


def _parse_vtt(content: str) -> list[dict]:
    segments = []
    lines = content.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            times = line.split("-->")
            start = _time_str_to_seconds(times[0].strip())
            end = _time_str_to_seconds(times[1].strip().split()[0])
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                text_lines.append(lines[i].strip())
                i += 1
            text = " ".join(text_lines)
            if text:
                segments.append({"start": start, "end": end, "text": text})
        else:
            i += 1
    return segments


def _parse_srt(content: str) -> list[dict]:
    """SRT 格式与 VTT 格式类似，复用 VTT 解析器"""
    return _parse_vtt(content)


def _time_str_to_seconds(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(parts[0])


# ── Bilibili 字幕 (bilibili-api-python + Credential) ──
# 参考: https://github.com/dalitoytos-dotcom/bilibili-subtitle-fetcher

async def _fetch_bilibili_subtitles(
    url: str,
    on_batch=None,
    allow_whisper: bool = True,
    user_id: int | None = None,
) -> list[dict]:
    """通过 bilibili-api-python 获取字幕（WBI 签名 + Cookie）"""
    m = re.search(r"/video/(BV[\w]+)", url, re.I)
    if not m:
        return []
    bvid = m.group(1)
    p_match = re.search(r"[?&]p=(\d+)", url)
    page = int(p_match.group(1)) if p_match else 1

    try:
        from bilibili_api import video as bili_video
        from app.services import bilibili_auth

        credential = bilibili_auth.get_api_credential(user_id=user_id)
        if not credential:
            print("[subtitle] bilibili: no credential — please login via Web UI")
            raise RuntimeError("请先在本站点击「B站登录」扫码登录")

        v = bili_video.Video(bvid=bvid, credential=credential)
        info = await v.get_info()
        cid = info["cid"]
        for p_info in info.get("pages", []):
            if p_info.get("page") == page:
                cid = p_info["cid"]
                break
        print(f"[subtitle] bilibili-api: bvid={bvid}, page={page}, cid={cid}")

        sub_info = await v.get_subtitle(cid=cid)
        subtitles = (sub_info or {}).get("subtitles", [])
        print(f"[subtitle] bilibili-api: found {len(subtitles)} subtitle track(s)")
        for s in subtitles:
            print(f"  track: lan={s.get('lan')}, doc={s.get('lan_doc')}")

        if not subtitles:
            print("[subtitle] bilibili: this video has no subtitle tracks")
            return []

        # 优先英文字幕，其次 AI 字幕
        track = None
        for s in subtitles:
            if "en" in (s.get("lan") or "").lower():
                track = s
                break
        if not track:
            for s in subtitles:
                lan = (s.get("lan") or "").lower()
                if "ai" in lan or "zh" in lan:
                    track = s
                    break
        if not track:
            track = subtitles[0]

        sub_url = track.get("subtitle_url", "")
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url

        async with httpx.AsyncClient(timeout=30, headers=_BILI_HEADERS) as client:
            resp = await client.get(sub_url)
            parsed = _parse_bilibili_subtitle(resp.json())
            print(f"[subtitle] bilibili-api: parsed {len(parsed)} segments")
            return parsed

    except Exception as e:
        print(f"[subtitle] bilibili-api failed: {e}")
        return []


def _parse_bilibili_subtitle(data: dict) -> list[dict]:
    segments = []
    for item in data.get("body", []):
        start = item.get("from", 0)
        end = item.get("to", start + 2)
        text = item.get("content", "").strip()
        if text:
            segments.append({"start": start, "end": end, "text": text})
    return segments


# ── Whisper ASR 回退 ───────────────────────────────────
async def _whisper_fallback(url: str, source: str, on_batch=None, user_id: int | None = None) -> list[dict]:
    """无字幕时，下载音频并用 faster-whisper 转录
    
    Args:
        url: 视频 URL
        source: 视频来源
        on_batch: 流式保存回调，每 20 条调用一次
    """
    print(f"[subtitle] No subtitles found, falling back to Whisper ASR for {url}")
    try:
        if source == "bilibili":
            audio_path = await _download_bilibili_audio_async(url, user_id=user_id)
        else:
            audio_path = await asyncio.to_thread(_download_ytdlp_audio, url, tempfile.mkdtemp())
        if not audio_path:
            return []
        if on_batch:
            # 流式转录：每批保存到 DB
            segments = await asyncio.to_thread(
                _transcribe_with_whisper_streaming, audio_path, on_batch, 20
            )
        else:
            segments = await asyncio.to_thread(_transcribe_with_whisper, audio_path)
        Path(audio_path).unlink(missing_ok=True)
        return segments
    except Exception as e:
        print(f"[subtitle] Whisper ASR failed: {e}")
        return []


async def _download_bilibili_audio_async(url: str, user_id: int | None = None) -> Optional[str]:
    """用 bilibili-api-python 异步下载 Bilibili 音频"""
    m = re.search(r"/video/(BV[\w]+)", url)
    if not m:
        return None
    bvid = m.group(1)
    p_match = re.search(r"[?&]p=(\d+)", url)
    page = int(p_match.group(1)) if p_match else 1

    from bilibili_api import video as bili_video
    from app.services import bilibili_auth

    credential = bilibili_auth.get_api_credential(user_id=user_id)
    v = bili_video.Video(bvid=bvid, credential=credential)
    download_url_data = await v.get_download_url(page_index=page)
    print(f"[subtitle] bilibili: got download URL data")

    audio_urls = []
    dash = download_url_data.get("dash", {})
    if dash:
        for audio in dash.get("audio", []):
            audio_urls.append(audio["base_url"])
    if not audio_urls:
        durl = download_url_data.get("durl", [])
        if durl:
            audio_urls.append(durl[0]["url"])
    if not audio_urls:
        print("[subtitle] bilibili: no audio URL found")
        return None

    print(f"[subtitle] bilibili: found {len(audio_urls)} audio URL(s)")

    tmp_dir = tempfile.mkdtemp()
    output_path = str(Path(tmp_dir) / "audio.m4s")
    audio_url = audio_urls[0]
    headers = {
        "User-Agent": _BILI_HEADERS["User-Agent"],
        "Referer": "https://www.bilibili.com/",
    }

    def _do_download():
        with httpx.stream("GET", audio_url, headers=headers, timeout=120, follow_redirects=True) as resp:
            if resp.status_code != 200:
                print(f"[subtitle] bilibili: audio download failed: {resp.status_code}")
                return None
            with open(output_path, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
        return output_path

    return await asyncio.to_thread(_do_download)


def _download_ytdlp_audio(url: str, tmp_dir: str) -> Optional[str]:
    """用 yt-dlp 下载音频"""
    import yt_dlp
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(Path(tmp_dir) / "audio.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    for f in Path(tmp_dir).iterdir():
        return str(f)
    return None


def _transcribe_with_whisper(audio_path: str) -> list[dict]:
    """用 faster-whisper 转录音频，自动检测语言"""
    from faster_whisper import WhisperModel

    wav_path = audio_path
    if audio_path.endswith(".m4s"):
        wav_path = _convert_to_wav(audio_path)
        if not wav_path:
            print("[whisper] ffmpeg conversion failed")
            return []

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(wav_path, beam_size=5)
    detected_lang = info.language if info else "unknown"
    print(f"[whisper] detected language: {detected_lang}")
    result = []
    for seg in segments_iter:
        text = seg.text.strip()
        if text:
            result.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": text,
                "lang": detected_lang,
            })
    if wav_path != audio_path:
        Path(wav_path).unlink(missing_ok=True)
    return result


def _transcribe_with_whisper_streaming(audio_path: str, on_batch=None, batch_size: int = 20) -> list[dict]:
    """流式 Whisper 转录：每 batch_size 条调用 on_batch 回调保存一次
    
    Args:
        audio_path: 音频文件路径
        on_batch: 回调函数，接收 list[dict]，返回 None
        batch_size: 每批保存的条数
    
    Returns:
        全部字幕段列表
    """
    from faster_whisper import WhisperModel

    wav_path = audio_path
    if audio_path.endswith(".m4s"):
        wav_path = _convert_to_wav(audio_path)
        if not wav_path:
            print("[whisper] ffmpeg conversion failed")
            return []

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(wav_path, beam_size=5)
    detected_lang = info.language if info else "unknown"
    print(f"[whisper] detected language: {detected_lang}")
    
    result = []
    batch = []
    for seg in segments_iter:
        text = seg.text.strip()
        if text:
            item = {
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": text,
                "lang": detected_lang,
            }
            result.append(item)
            batch.append(item)
            if len(batch) >= batch_size and on_batch:
                print(f"[whisper] streaming save: {len(result)} segments so far")
                on_batch(batch)
                batch = []
    
    # 保存剩余的
    if batch and on_batch:
        print(f"[whisper] streaming save: final {len(result)} segments")
        on_batch(batch)
    
    if wav_path != audio_path:
        Path(wav_path).unlink(missing_ok=True)
    return result


def _convert_to_wav(input_path: str) -> Optional[str]:
    """用 ffmpeg 将音频转换为 WAV (16kHz mono)"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("[whisper] ffmpeg not found in PATH")
        return None
    output_path = str(Path(input_path).with_suffix(".wav"))
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-f", "wav", output_path],
            capture_output=True,
            timeout=300,
        )
        if Path(output_path).exists():
            return output_path
    except Exception as e:
        print(f"[whisper] ffmpeg conversion error: {e}")
    return None
