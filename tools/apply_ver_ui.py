from pathlib import Path
import json
import re

root = Path(r"D:\lian\praPro\h-videoE")
js_p = root / "app" / "static" / "m" / "app.js"
js = js_p.read_text(encoding="utf-8")

paint_fn = '''
  function paintMineVersion(remote) {
    const el = document.getElementById('mineWebVer');
    if (!el) return;
    const apk = nativeApkMeta();
    const apkLabel = apk.isApp || nativeBridge()
      ? `${apk.name || 'App'} (${apk.code || 0})`
      : '网页版';
    const latest = String((remote && remote.web_content_version) || (cachedAppVersion && cachedAppVersion.web_content_version) || '').trim();
    const local = localWebVersion() || latest || '—';
    if (latest && latest !== local) {
      el.innerHTML = `当前网页 ${escapeHtml(local)}<br/>最新版本 ${escapeHtml(latest)} · App ${escapeHtml(apkLabel)}`;
    } else {
      el.textContent = `当前网页 ${latest || local}（已是最新） · App ${apkLabel}`;
    }
  }

'''

anchor = "  function nativeApkMeta() {"
if paint_fn.strip().split("\n")[0] in js:
    print("paintMineVersion already present")
else:
    if anchor not in js:
        raise SystemExit("nativeApkMeta anchor missing")
    js = js.replace(anchor, paint_fn + anchor, 1)
    print("inserted paintMineVersion")

old_check = """      const remote = await fetchAppVersion();
      const localWeb = localWebVersion();
      const webNewer = !!remote.web_content_version && remote.web_content_version !== localWeb;"""
new_check = """      const remote = await fetchAppVersion();
      paintMineVersion(remote);
      const localWeb = localWebVersion();
      const webNewer = !!remote.web_content_version && remote.web_content_version !== localWeb;"""
if old_check not in js:
    raise SystemExit("check fetch block missing")
js = js.replace(old_check, new_check, 1)

old_toast = """      if (!webNewer && !apkNewer) {
        if (!silent) toast('已是最新版本');
        if (state.tab === 'mine') renderMine();
        return { webNewer, apkNewer, remote };
      }"""
new_toast = """      if (!webNewer && !apkNewer) {
        if (!silent) toast('已是最新版本 ' + (remote.web_content_version || ''));
        return { webNewer, apkNewer, remote };
      }"""
if old_toast not in js:
    raise SystemExit("already-latest block missing")
js = js.replace(old_toast, new_toast, 1)

old_label = """        <p class="m-muted" style="margin:0 0 12px;font-size:0.82rem;">当前网页 ${escapeHtml(webLabel)} · App ${escapeHtml(apkLabel)}</p>"""
new_label = """        <p class="m-muted" id="mineWebVer" style="margin:0 0 12px;font-size:0.82rem;">当前网页 ${escapeHtml(webLabel)} · App ${escapeHtml(apkLabel)}</p>"""
if old_label not in js:
    raise SystemExit("version label missing")
js = js.replace(old_label, new_label, 1)

# after renderMine sets innerHTML, refresh version line from cache
old_bind = "$('#checkUpdateBtn')?.addEventListener('click', () => checkForUpdate());"
new_bind = """paintMineVersion(cachedAppVersion);
    $('#checkUpdateBtn')?.addEventListener('click', () => checkForUpdate());"""
if old_bind not in js:
    raise SystemExit("check btn bind missing")
js = js.replace(old_bind, new_bind, 1)

js_p.write_text(js, encoding="utf-8")
print("app.js patched")

# bump only mobile cache + app-version.json
html_p = root / "app" / "static" / "m" / "index.html"
html = html_p.read_text(encoding="utf-8")
html = html.replace("20260817.5", "20260817.6")
html = html.replace("20260817.4", "20260817.6")
html_p.write_text(html, encoding="utf-8")
print("html", set(re.findall(r"\\?v=[\\d.]+", html)))

jp = root / "app" / "static" / "m" / "app-version.json"
data = json.loads(jp.read_text(encoding="utf-8"))
data["web_content_version"] = "20260817.6"
data["notes"] = "检测最新版本会立刻显示服务器版本号"
jp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
print("json", data["web_content_version"])
