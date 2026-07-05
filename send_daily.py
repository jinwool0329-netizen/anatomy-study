#!/usr/bin/env python3
"""
매일 실행되어 '오늘의 해부학 용어 30개'와 공부/시험 링크를 카카오톡(나에게 보내기)으로 발송한다.

  python3 send_daily.py            # 다음 날짜(day) 진행 + 실제 발송
  python3 send_daily.py --dry-run  # 발송하지 않고 메시지 미리보기만 출력
  python3 send_daily.py --day 5    # 특정 day 를 강제로 발송 (상태 갱신 안 함)
  python3 send_daily.py --peek     # 다음 day 내용을 발송/갱신 없이 미리보기

발송 흐름:
  ① Day N 용어를 한글·영어·라틴어+관련지식 블록으로, 200자 제한에 맞춰 여러 카톡 메시지로 발송
     (채팅을 읽으며 그대로 공부. include_knowledge_line=false 면 용어만 간결히)
  ② 마지막에 '📝 시험 보기' 링크 버튼 메시지 발송  ({quiz_base_url}?day=N&tab=test)
링크 페이지는 시험 탭으로 바로 열리며, [📖 오늘 공부] 탭도 복습용으로 들어있다.
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
STATE = os.path.join(HERE, "state.json")
WORDS = os.path.join(HERE, "data", "words.json")
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
TEXT_LIMIT = 190  # 카카오 텍스트 템플릿 text 한도(200) 안전 여유


def load_json(path, default=None):
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    if default is not None:
        return default
    sys.exit(f"파일 없음: {path}")


def save_json(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def refresh_access_token(cfg):
    params = {
        "grant_type": "refresh_token",
        "client_id": cfg["rest_api_key"],
        "refresh_token": cfg["refresh_token"],
    }
    if cfg.get("client_secret"):  # 앱에 클라이언트 시크릿이 켜져 있으면 필수
        params["client_secret"] = cfg["client_secret"]
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request("https://kauth.kakao.com/oauth/token", data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        tok = json.loads(r.read().decode())
    # 카카오는 refresh_token 이 갱신되어 내려올 때가 있으므로 저장
    if tok.get("refresh_token"):
        cfg["refresh_token"] = tok["refresh_token"]
        save_json(CONFIG, cfg)
    return tok["access_token"]


def send_text(access_token, text, link_url=None, button_title=None):
    template = {"object_type": "text", "text": text}
    if link_url:
        template["link"] = {"web_url": link_url, "mobile_web_url": link_url}
        template["button_title"] = button_title or "열기"
    else:
        template["link"] = {"web_url": "", "mobile_web_url": ""}
    data = urllib.parse.urlencode({"template_object": json.dumps(template, ensure_ascii=False)}).encode()
    req = urllib.request.Request(MEMO_URL, data=data, method="POST",
                                 headers={"Authorization": "Bearer " + access_token})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def word_line(i, w, with_knowledge):
    """카톡에서 채팅 읽듯 공부하도록 용어+영어+라틴어(+관련지식)를 한 블록으로."""
    s = f"{i}. {w.get('ko','')}"
    if w.get("en"):
        s += "\n   " + w["en"] + (f" · {w['la']}" if w.get("la") else "")
    if with_knowledge and w.get("knowledge"):
        s += "\n   " + w["knowledge"]
    return s


def chunk_lines(header, lines, limit=TEXT_LIMIT):
    """헤더 + 라인들을 limit 자 이내의 여러 메시지로 분할."""
    msgs, cur = [], header
    for ln in lines:
        piece = ("\n" + ln) if cur else ln
        if len(cur) + len(piece) > limit and cur:
            msgs.append(cur)
            cur = ln
        else:
            cur += piece
    if cur:
        msgs.append(cur)
    return msgs


def build_messages(day, words, cfg):
    per_day = cfg.get("per_day", 30)
    block = words[(day - 1) * per_day: day * per_day]
    if not block:
        return None, None
    with_k = cfg.get("include_knowledge_line", False)
    sys_hint = block[0].get("system", "")
    header = f"🦴 [Day {day}] 오늘의 해부학 용어 {len(block)}개\n계통: {sys_hint}\n"
    lines = [word_line(i + 1, w, with_k) for i, w in enumerate(block)]
    text_msgs = chunk_lines(header, lines)
    link = cfg["quiz_base_url"].rstrip("/") + "/" if cfg["quiz_base_url"].endswith("quiz") \
        else cfg["quiz_base_url"]
    link = link + ("&" if "?" in link else "?") + "day=" + str(day) + "&pd=" + str(per_day) + "&tab=test"
    link_msg = (f"📝 오늘 시험 보기\n"
                f"위 용어들을 다 외웠으면, Day {day}까지 누적된 단어로 시험을 봅니다. "
                f"아래 버튼을 눌러 시작하세요!")
    return text_msgs, (link_msg, link)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="발송 없이 미리보기")
    ap.add_argument("--peek", action="store_true", help="상태 갱신/발송 없이 다음 day 미리보기")
    ap.add_argument("--day", type=int, help="특정 day 강제 발송(상태 미갱신)")
    args = ap.parse_args()

    cfg = load_json(CONFIG, default=None)
    words = load_json(WORDS)["words"]
    state = load_json(STATE, default={"day": 0})

    if args.day:
        day, advance = args.day, False
    else:
        day, advance = state.get("day", 0) + 1, True

    max_day = (len(words) + cfg.get("per_day", 30) - 1) // cfg.get("per_day", 30)
    if day > max_day:
        print(f"모든 용어({max_day}일치)를 다 보냈어요. words.json 에 용어를 더 추가하세요.")
        return

    text_msgs, link_pair = build_messages(day, words, cfg)
    if not text_msgs:
        print("해당 day 에 용어가 없습니다."); return
    link_msg, link_url = link_pair

    preview = (args.dry_run or args.peek)
    if preview:
        print(f"===== Day {day} 미리보기 =====")
        for i, m in enumerate(text_msgs, 1):
            print(f"\n--- 메시지 {i} ---\n{m}")
        print(f"\n--- 링크 메시지 ---\n{link_msg}\n[버튼: 📝 시험 보러가기] → {link_url}")
        if args.peek:
            return

    if args.dry_run:
        return

    token = refresh_access_token(cfg)
    for m in text_msgs:
        send_text(token, m)
        time.sleep(0.4)  # 다량 발송 시 카카오 속도제한 여유
    send_text(token, link_msg, link_url=link_url, button_title="📝 시험 보러가기")
    print(f"✅ Day {day} 발송 완료 ({len(text_msgs)}개 용어 메시지 + 링크).")

    if advance:
        state["day"] = day
        save_json(STATE, state)


if __name__ == "__main__":
    main()
