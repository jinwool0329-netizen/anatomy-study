#!/usr/bin/env python3
"""
카카오 '나에게 보내기' 최초 1회 인증 도구.
REST API 키로 로그인 인증코드를 받아 refresh_token 을 발급받고 config.json 에 저장한다.

사전 준비 (developers.kakao.com):
  1) 애플리케이션 추가 → '앱 키'의 REST API 키 복사
  2) [카카오 로그인] 활성화 ON, Redirect URI 등록 (예: https://localhost:8080)
  3) [카카오 로그인 > 동의항목] '카카오톡 메시지 전송(talk_message)' 사용 설정
사용:
  python3 kakao_auth.py
"""
import json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")


def post_form(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def main():
    if os.path.exists(CONFIG):
        cfg = json.load(open(CONFIG, encoding="utf-8"))
    else:
        example = os.path.join(HERE, "config.example.json")
        cfg = json.load(open(example, encoding="utf-8")) if os.path.exists(example) else {}

    key = cfg.get("rest_api_key") or input("카카오 REST API 키: ").strip()
    redirect = cfg.get("redirect_uri") or input("Redirect URI (예: https://localhost:8080): ").strip()
    cfg["rest_api_key"], cfg["redirect_uri"] = key, redirect

    authorize = ("https://kauth.kakao.com/oauth/authorize?"
                 + urllib.parse.urlencode({
                     "client_id": key,
                     "redirect_uri": redirect,
                     "response_type": "code",
                     "scope": "talk_message",
                 }))
    print("\n[1] 아래 주소를 브라우저에서 열고 카카오 로그인/동의를 진행하세요:\n")
    print("    " + authorize + "\n")
    print("[2] 로그인 후 이동한 주소(" + redirect + "?code=...) 에서 code 값을 복사하세요.")
    code = input("\ncode 값 붙여넣기: ").strip()

    print("\n토큰 발급 중…")
    try:
        tok = post_form("https://kauth.kakao.com/oauth/token", {
            "grant_type": "authorization_code",
            "client_id": key,
            "redirect_uri": redirect,
            "code": code,
        })
    except urllib.error.HTTPError as e:
        print("발급 실패:", e.read().decode()); sys.exit(1)

    if "refresh_token" not in tok:
        print("응답에 refresh_token 이 없습니다:", tok); sys.exit(1)

    cfg["refresh_token"] = tok["refresh_token"]
    cfg.setdefault("quiz_base_url", "https://YOURNAME.github.io/anatomy-study/quiz/")
    cfg.setdefault("per_day", 30)
    cfg.setdefault("include_knowledge_line", True)
    json.dump(cfg, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n✅ 완료! config.json 에 refresh_token 저장됨.")
    print("이제 python3 send_daily.py --dry-run 으로 테스트해 보세요.")


if __name__ == "__main__":
    main()
