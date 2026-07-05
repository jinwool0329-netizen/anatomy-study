#!/usr/bin/env python3
"""
해부학 암기봇 로컬 대시보드.
컴퓨터 안에서만(127.0.0.1) 도는 제어판으로, 브라우저에서 상태 확인 + 설정 변경 + 즉시 발송을 한다.

실행:
  python3 dashboard.py          # 서버 켜고 브라우저 자동으로 열림 (http://127.0.0.1:7788)
  python3 dashboard.py --no-open
끄기: 터미널에서 Ctrl+C
"""
import json, os, re, subprocess, sys, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
STATE = os.path.join(HERE, "state.json")
WORDS = os.path.join(HERE, "data", "words.json")
PLIST_SRC = os.path.join(HERE, "com.jinwoo.anatomy.plist")
PLIST_DST = os.path.expanduser("~/Library/LaunchAgents/com.jinwoo.anatomy.plist")
LOG = os.path.join(HERE, "send.log")
PORT = 7788

sys.path.insert(0, HERE)
import send_daily as sd  # 발송/토큰 로직 재사용


def load(path, default=None):
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    return default


def save(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def launchd_loaded():
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
        return "com.jinwoo.anatomy" in out
    except Exception:
        return False


def schedule_time():
    """설치된 plist에서 Hour/Minute 읽기."""
    txt = load_text(PLIST_DST) or load_text(PLIST_SRC) or ""
    h = re.search(r"<key>Hour</key>\s*<integer>(\d+)</integer>", txt)
    m = re.search(r"<key>Minute</key>\s*<integer>(\d+)</integer>", txt)
    return (int(h.group(1)) if h else 8, int(m.group(1)) if m else 0)


def load_text(path):
    return open(path, encoding="utf-8").read() if os.path.exists(path) else None


def set_schedule(hour, minute):
    txt = load_text(PLIST_SRC)
    txt = re.sub(r"(<key>Hour</key>\s*<integer>)\d+(</integer>)",
                 lambda m: m.group(1) + str(hour) + m.group(2), txt)
    txt = re.sub(r"(<key>Minute</key>\s*<integer>)\d+(</integer>)",
                 lambda m: m.group(1) + str(minute) + m.group(2), txt)
    open(PLIST_SRC, "w", encoding="utf-8").write(txt)
    os.makedirs(os.path.dirname(PLIST_DST), exist_ok=True)
    open(PLIST_DST, "w", encoding="utf-8").write(txt)
    subprocess.run(["launchctl", "unload", PLIST_DST], capture_output=True)
    r = subprocess.run(["launchctl", "load", PLIST_DST], capture_output=True, text=True)
    return r.returncode == 0


def status():
    cfg = load(CONFIG, {}) or {}
    st = load(STATE, {"day": 0}) or {"day": 0}
    words = (load(WORDS, {}) or {}).get("words", [])
    per_day = cfg.get("per_day", 30)
    total = len(words)
    total_days = (total + per_day - 1) // per_day if per_day else 0
    day = st.get("day", 0)
    hour, minute = schedule_time()
    nxt = words[day * per_day] if day * per_day < total else None
    return {
        "day": day, "total_days": total_days, "per_day": per_day,
        "total_words": total, "remaining_days": max(0, total_days - day),
        "next_system": (nxt or {}).get("system", "—"),
        "next_region": (nxt or {}).get("region", ""),
        "include_knowledge": cfg.get("include_knowledge_line", True),
        "quiz_base_url": cfg.get("quiz_base_url", ""),
        "has_token": bool(cfg.get("refresh_token")),
        "hour": hour, "minute": minute,
        "scheduled": launchd_loaded(),
        "log": (load_text(LOG) or "").splitlines()[-15:],
    }


def run_send(mode, day=None):
    args = [sys.executable, os.path.join(HERE, "send_daily.py")]
    if mode == "peek":
        args.append("--peek")
    elif mode == "day" and day:
        args += ["--day", str(int(day))]
    # mode == "now" → 인자 없이 (진도 +1 후 발송)
    r = subprocess.run(args, capture_output=True, text=True, cwd=HERE, timeout=120)
    return (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")


def send_test():
    cfg = load(CONFIG)
    token = sd.refresh_access_token(cfg)
    link = cfg["quiz_base_url"].rstrip("/") + "/?day=1&pd=%d&tab=test" % cfg.get("per_day", 30)
    sd.send_text(token, "🔔 대시보드 테스트 메시지예요! 잘 도착하면 설정 정상입니다.\n"
                        "시험 페이지 👇\n" + link)
    return "테스트 메시지 발송 완료 (카톡 확인)"


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html")
        if path == "/api/status":
            return self._send(200, json.dumps(status(), ensure_ascii=False))
        self._send(404, "{}")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or "{}") if n else {}
        try:
            if path == "/api/config":
                cfg = load(CONFIG)
                if "per_day" in body: cfg["per_day"] = max(1, int(body["per_day"]))
                if "include_knowledge_line" in body: cfg["include_knowledge_line"] = bool(body["include_knowledge_line"])
                save(CONFIG, cfg)
                return self._send(200, json.dumps({"ok": True}))
            if path == "/api/schedule":
                ok = set_schedule(int(body["hour"]) % 24, int(body["minute"]) % 60)
                return self._send(200, json.dumps({"ok": ok}))
            if path == "/api/setday":
                st = load(STATE, {"day": 0}); st["day"] = max(0, int(body["day"])); save(STATE, st)
                return self._send(200, json.dumps({"ok": True}))
            if path == "/api/send":
                out = run_send(body.get("mode", "now"), body.get("day"))
                return self._send(200, json.dumps({"ok": True, "output": out}, ensure_ascii=False))
            if path == "/api/test":
                return self._send(200, json.dumps({"ok": True, "output": send_test()}, ensure_ascii=False))
        except Exception as e:
            return self._send(200, json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        self._send(404, "{}")


PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>해부학 암기봇 대시보드</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#1a1d21;--sub:#657;--line:#e5e8ec;--brand:#3a6df0;--ok:#12915f;--bad:#d23b4e;--chip:#eef1f6}
@media(prefers-color-scheme:dark){:root{--bg:#14161a;--card:#1e2127;--ink:#f2f4f7;--sub:#9aa4b0;--line:#2c313a;--brand:#5b8bff;--ok:#3ddc9a;--bad:#ff7085;--chip:#282d36}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Apple SD Gothic Neo",system-ui,sans-serif;line-height:1.5}
.wrap{max-width:720px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:20px;margin:6px 0 2px;font-weight:800}.muted{color:var(--sub);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin-top:14px}
.card h2{font-size:15px;margin:0 0 12px;font-weight:800}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.stat{background:var(--chip);border-radius:12px;padding:12px;text-align:center}
.stat b{display:block;font-size:22px;font-weight:900}.stat span{font-size:11px;color:var(--sub)}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
input[type=number]{width:70px;padding:8px;border:1px solid var(--line);border-radius:9px;background:var(--card);color:var(--ink);font-size:15px;font-weight:700}
button{border:none;border-radius:10px;padding:10px 14px;font-size:14px;font-weight:800;cursor:pointer;background:var(--brand);color:#fff}
button.ghost{background:var(--card);color:var(--ink);border:1px solid var(--line)}
button:active{transform:scale(.98)}button:disabled{opacity:.5;cursor:default}
.pill{font-size:12px;font-weight:700;padding:3px 10px;border-radius:999px}
.pill.on{background:rgba(18,145,95,.15);color:var(--ok)}.pill.off{background:rgba(210,59,78,.15);color:var(--bad)}
label.sw{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:600}
pre{background:var(--chip);border-radius:10px;padding:12px;font-size:12px;overflow:auto;max-height:260px;white-space:pre-wrap;margin:10px 0 0}
.note{font-size:12px;color:var(--sub);margin-top:8px}
.sp{flex:1}
</style></head><body><div class="wrap">
<h1>🦴 해부학 암기봇 대시보드</h1>
<div class="muted">컴퓨터 안에서만 도는 제어판 · <span id="sched"></span></div>

<div class="card"><h2>진행 상태</h2>
  <div class="grid">
    <div class="stat"><b id="s_day">–</b><span>현재 Day</span></div>
    <div class="stat"><b id="s_total">–</b><span>총 학습일</span></div>
    <div class="stat"><b id="s_rem">–</b><span>남은 일수</span></div>
    <div class="stat"><b id="s_pd">–</b><span>하루 단어</span></div>
  </div>
  <div class="note">총 용어 <b id="s_words">–</b>개 · 다음 발송 계통: <b id="s_next">–</b> · 토큰 <span id="s_tok"></span></div>
</div>

<div class="card"><h2>지금 발송</h2>
  <div class="row">
    <button onclick="send('now')">오늘 분량 발송 (진도 +1)</button>
    <button class="ghost" onclick="send('peek')">미리보기(발송 안 함)</button>
    <button class="ghost" onclick="test()">테스트 메시지</button>
  </div>
  <div class="row" style="margin-top:10px">
    <span class="muted">특정 Day 발송(진도 유지):</span>
    <input type="number" id="sendDay" min="1" value="1">
    <button class="ghost" onclick="send('day')">이 Day 발송</button>
  </div>
</div>

<div class="card"><h2>발송 시간</h2>
  <div class="row">
    <input type="number" id="hh" min="0" max="23"> 시
    <input type="number" id="mm" min="0" max="59"> 분
    <button onclick="saveSched()">저장 & 적용</button>
    <span class="sp"></span><span id="schedPill" class="pill"></span>
  </div>
  <div class="note">저장하면 매일 자동발송(launchd)이 이 시각으로 재설정돼요. 맥이 켜져 있어야 발송됩니다.</div>
</div>

<div class="card"><h2>하루 단어 수 · 옵션</h2>
  <div class="row">
    <input type="number" id="pd" min="1" max="100"> 개씩
    <label class="sw"><input type="checkbox" id="knw"> 카톡에 관련 지식 포함</label>
    <button onclick="saveCfg()">저장</button>
  </div>
  <div class="note">단어 수를 바꾸면 발송·시험 링크에 자동 반영돼요. (온라인 시험 페이지에도 즉시 적용 — 링크의 pd 값으로 전달)</div>
</div>

<div class="card"><h2>진도 조절</h2>
  <div class="row">
    <span class="muted">현재 Day를</span>
    <input type="number" id="setDay" min="0">
    <span class="muted">로 설정</span>
    <button class="ghost" onclick="setDay()">적용</button>
  </div>
  <div class="note">0으로 하면 다음 발송이 Day 1부터 다시 시작돼요.</div>
</div>

<div class="card"><h2>실행 로그</h2><pre id="log">불러오는 중…</pre></div>
</div>
<script>
const $=id=>document.getElementById(id);
async function api(path,body){const o={method:body?'POST':'GET'};if(body){o.headers={'Content-Type':'application/json'};o.body=JSON.stringify(body)}const r=await fetch(path,o);return r.json()}
async function load(){const s=await api('/api/status');
  $('s_day').textContent=s.day;$('s_total').textContent=s.total_days;$('s_rem').textContent=s.remaining_days;
  $('s_pd').textContent=s.per_day;$('s_words').textContent=s.total_words;
  $('s_next').textContent=s.next_system+(s.next_region?(' · '+s.next_region):'');
  $('s_tok').innerHTML=s.has_token?'<b style="color:var(--ok)">정상</b>':'<b style="color:var(--bad)">없음</b>';
  $('hh').value=s.hour;$('mm').value=s.minute;$('pd').value=s.per_day;$('knw').checked=s.include_knowledge;
  $('setDay').value=s.day;
  const two=n=>String(n).padStart(2,'0');
  $('sched').textContent='매일 '+two(s.hour)+':'+two(s.minute)+' 자동발송';
  const p=$('schedPill');p.textContent=s.scheduled?'자동발송 ON':'자동발송 OFF';p.className='pill '+(s.scheduled?'on':'off');
  $('log').textContent=(s.log&&s.log.length)?s.log.join('\n'):'(아직 실행 로그 없음)';
}
async function send(mode){const body={mode};if(mode==='day')body.day=+$('sendDay').value;
  showLog('발송 중… (여러 메시지는 시간이 조금 걸려요)');const r=await api('/api/send',body);showLog(r.output||r.error);load()}
async function test(){showLog('테스트 발송 중…');const r=await api('/api/test',{});showLog(r.output||r.error);load()}
async function saveSched(){const r=await api('/api/schedule',{hour:+$('hh').value,minute:+$('mm').value});showLog(r.ok?'발송 시간 적용됨':('실패: '+(r.error||'')));load()}
async function saveCfg(){const r=await api('/api/config',{per_day:+$('pd').value,include_knowledge_line:$('knw').checked});showLog(r.ok?'설정 저장됨':('실패: '+(r.error||'')));load()}
async function setDay(){const r=await api('/api/setday',{day:+$('setDay').value});showLog(r.ok?'진도 변경됨':('실패: '+(r.error||'')));load()}
function showLog(t){$('log').textContent=t}
load();setInterval(load,15000);
</script></body></html>"""


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = "http://127.0.0.1:%d" % PORT
    print("대시보드 실행 중 →", url, "   (끄기: Ctrl+C)")
    if "--no-open" not in sys.argv:
        subprocess.run(["open", url])
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n대시보드 종료.")


if __name__ == "__main__":
    main()
