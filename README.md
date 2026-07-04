# 🦴 해부학 용어 암기 봇 (카카오톡 + 웹 시험)

매일 아침 **해부학 용어 30개**를 카카오톡으로 받고, 함께 오는 링크로 들어가
**관련 지식과 함께 공부**한 뒤 **누적(적립식) 시험**을 봅니다.
어제·그제 외운 단어가 계속 쌓여서 다시 출제되고, 틀린 단어일수록 더 자주 나옵니다.

```
매일 08:00  ──▶  카카오톡 "나에게 보내기"
                 ├─ Day N 용어 30개 = 한글·영어·라틴어 + 관련 지식
                 │    (채팅 읽듯이 스크롤하며 공부. 용어당 1개꼴, 약 27개 메시지)
                 └─ 🔗 시험 링크  ({quiz_base_url}?day=N&tab=test)
                        └─ 📝 누적 시험: Day 1~N 누적 출제 · 자동 채점 · 기록
```
> 공부는 **카톡 메시지 자체를 읽으며** 하고, 링크는 **시험 전용**입니다.
> (링크 페이지에도 📖 오늘 공부 탭이 있어 복습용으로 볼 수 있어요.)

- 서버 불필요: 웹 시험은 **정적 사이트로 한 번만 배포**, 매일 링크의 `?day=N` 숫자만 바뀝니다.
- 시험 기록/점수/틀린 단어는 브라우저 `localStorage`에 누적 저장됩니다(한 브라우저에서 계속 보세요).
- 파이썬 표준 라이브러리만 사용(추가 설치 없음).

---

## 폴더 구성
```
anatomy-study/
├── data/words.json          # 해부학 용어 뱅크 (계통별, 순서대로 30개씩 하루 분량)
├── quiz/index.html          # 웹 공부·시험 페이지 (정적)
├── send_daily.py            # 매일 카카오톡 발송 스크립트
├── kakao_auth.py            # 카카오 최초 1회 인증 (refresh_token 발급)
├── config.example.json      # 설정 예시 → 복사해서 config.json 로 사용
├── com.jinwoo.anatomy.plist # macOS 매일 자동실행(launchd) 설정
└── README.md
```

---

## 설치 (한 번만)

### 1) 웹 시험 페이지 배포 — GitHub Pages 추천 (무료, 폰에서 접속 가능)
1. 이 폴더를 GitHub 저장소로 올립니다.
   ```
   cd anatomy-study
   git init && git add . && git commit -m "init"
   gh repo create anatomy-study --public --source=. --push   # 또는 웹에서 repo 생성 후 push
   ```
2. GitHub 저장소 → **Settings → Pages → Branch: main / root** 저장.
3. 몇 분 뒤 접속 주소가 생깁니다:
   `https://<본인아이디>.github.io/anatomy-study/quiz/`
   → 이 주소가 `quiz_base_url` 입니다. (폰 브라우저로 열리는지 먼저 확인)

> ⚠️ `config.json`, `send.log` 등 개인 파일이 public 저장소에 올라가지 않도록
> `.gitignore`에 `config.json`, `state.json`, `*.log` 를 넣으세요.

### 2) 카카오 앱 만들기 + 인증
1. https://developers.kakao.com → **내 애플리케이션 → 애플리케이션 추가**.
2. **앱 키**에서 `REST API 키` 복사.
3. **카카오 로그인** → 활성화 **ON**, **Redirect URI**에 `https://localhost:8080` 등록.
4. **카카오 로그인 → 동의항목**에서 **카카오톡 메시지 전송(talk_message)** 사용 설정.
5. 설정 파일 준비 후 인증 실행:
   ```
   cp config.example.json config.json      # rest_api_key, redirect_uri, quiz_base_url 채우기
   python3 kakao_auth.py                    # 안내대로 로그인→code 붙여넣기 → refresh_token 저장
   ```

### 3) 미리보기로 확인
```
python3 send_daily.py --peek        # 상태 변경/발송 없이 다음 날 내용 확인
python3 send_daily.py --dry-run     # 발송 직전 메시지 전체 미리보기
python3 send_daily.py --day 1       # Day 1 을 실제로 나에게 보내보기(테스트)
```
카카오톡 "나에게 보내기" 방으로 메시지가 오면 성공입니다.

### 4) 매일 자동 발송 (macOS)
```
# plist 안의 __PROJECT_PATH__ 를 실제 경로로 바꾼 뒤:
cp com.jinwoo.anatomy.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jinwoo.anatomy.plist
```
- 발송 시각은 plist의 `Hour`/`Minute`로 변경(수정 후 `unload`→`load`).
- 컴퓨터가 그 시각에 켜져 있어야 발송됩니다(맥 절전 시 깨어난 뒤 실행).

---

## 매일 어떻게 진행되나
- 실행할 때마다 `state.json`의 `day`가 1씩 올라가며 그 날 분량을 발송합니다.
- 시험은 **그날 신규 30개 + 이전 누적 단어 복습**으로 구성 → 링크의 `?day=N`이 누적 범위를 결정.
- 시험 페이지에서 복습 문제 수를 슬라이더로 조절할 수 있고, "틀린 것만 다시" 기능도 있습니다.

### 진도 관리
- 하루 건너뛰고 싶으면 아무것도 안 하면 됩니다(다음 실행 때 다음 day 진행).
- 특정 날짜 다시 보기: `python3 send_daily.py --day 3` (상태는 안 바뀜).
- 처음부터 다시: `state.json`을 `{"day":0}` 으로 수정.

---

## 용어 추가 / 커스터마이즈
- `data/words.json`의 `words` 배열에 항목을 추가하면 그만큼 학습일이 늘어납니다.
  ```json
  { "id": 301, "ko": "…", "en": "…", "la": "…",
    "system": "…", "region": "…", "knowledge": "…" }
  ```
  `id`는 순서대로, 30개 단위로 하루 분량이 됩니다. (같은 30개 블록은 같은 주제로 묶으면 좋아요.)
- `config.json`
  - `per_day`: 하루 단어 수(기본 30).
  - `include_knowledge_line`(기본 **true**): 카톡 메시지에 관련 지식 전체가 함께 와서 채팅 읽듯 공부합니다.
    `false` 로 바꾸면 용어(한글·영어)만 간결하게 와서 메시지 수가 2~3개로 줄어듭니다(지식은 링크 페이지에서 확인).

---

## 참고 / 한계
- 카카오 **나에게 보내기**는 본인에게 보내는 개인용 API라 채널/사업자 심사가 필요 없습니다.
- 카카오 텍스트 메시지는 200자 제한이 있어 30개 용어는 자동으로 여러 개의 메시지로 나눠 발송됩니다.
- `refresh_token` 은 약 2개월 유효하며, 매일 발송이 돌면 자동 갱신되어 계속 유지됩니다.
  오래 안 쓰면 만료될 수 있고, 그때는 `python3 kakao_auth.py`를 다시 실행하면 됩니다.
- 시험 기록은 시험 보는 **브라우저에 저장**됩니다. 폰에서 항상 같은 브라우저로 여세요.
