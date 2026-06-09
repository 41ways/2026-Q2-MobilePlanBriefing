"""
알뜰폰 대란 브리핑 자동화 스크립트
매일 아침 조건에 맞는 요금제를 스캔하고 이메일로 전송합니다.

필요한 GitHub Secrets:
  - GEMINI_API_KEY     : Google AI Studio에서 발급 (완전 무료)
  - GMAIL_ADDRESS      : 보내는 Gmail 주소 (받는 주소도 동일)
  - GMAIL_APP_PASSWORD : Gmail 앱 비밀번호 (16자리)
"""

import os
import json
import smtplib
import urllib.request
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

# ── 상수 ──────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)

PROMPT = """너는 국내 알뜰폰 커뮤니티(뽐뿌 휴대폰포럼, 알뜰폰포럼, 알고사, 모요, 세모통 등)의
실시간 동향을 감시하고 분석하는 수석 알뜰폰 비서야.
오늘 날짜 기준으로 최신 알뜰폰 요금제 시장을 분석해서 브리핑을 작성해줘.
검색은 모요(moyoplan.com), 세모통(smtong.co.kr), 뽐뿌 휴대폰포럼 등을 기준으로 판단해줘.

[양보 불가능한 철벽 필터 조건]
1. 통신망: 무조건 5G 망 필수
2. 데이터: 기본 제공 데이터 15GB 이상 필수
3. 제한 속도: 기본 데이터 소진 후 최소 3Mbps 무제한 필수 (1Mbps 이하 절대 안 됨)
4. 통화: 음성 통화 무제한 필수
5. 요금 조건: 평생 요금 불변 필수 (프로모션 기간 후 원상복구되는 요금제 탈락)
6. 월 요금: 30,000원 이하 필수

[결합 할인 적용 규칙]
- 가족 결합 할인 지원 여부 우선 확인
- 안 된다면 인터넷 결합 등 대안 결합 확인 후 명시
- 결합 할인 혜택이 없으면 '결합할인 없음'으로 표기

[응답 형식 — 이메일 본문용 HTML]
조건을 100% 만족하는 요금제가 있는 경우:

<div class="plan">
  <h2>📱 [통신사] - [요금제명]</h2>
  <ul>
    <li><b>월 요금:</b> X원 (평생 고정)</li>
    <li><b>데이터:</b> 5G 기본 XGB + 소진 후 3Mbps 무제한</li>
    <li><b>통화/문자:</b> 무제한</li>
    <li><b>결합할인:</b> 가족결합 가능 / 인터넷 결합만 가능 / 결합 없음</li>
  </ul>
  <div class="review">
    🔥 커뮤니티 한줄평 (추천도: ⭐⭐⭐⭐⭐)<br>
    - <b>여론:</b> ...<br>
    - <b>긴급도:</b> ...<br>
    - <b>경쟁력:</b> ...
  </div>
</div>

조건을 만족하는 요금제가 없는 경우:
<p class="none">🚫 오늘의 조건 충족 요금제: 없음</p>
이후 탈락 후보 1~2개를 위 양식으로 분석하고 <b>탈락 사유</b> 명시.

HTML 태그 외 마크다운은 사용하지 말 것. 스타일 태그는 포함하지 말 것."""

# 이메일 HTML 템플릿
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Apple SD Gothic Neo',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:32px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

      <!-- 헤더 -->
      <tr>
        <td style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:28px 32px;">
          <p style="margin:0;color:#f0a500;font-size:12px;letter-spacing:2px;">DAILY BRIEFING</p>
          <h1 style="margin:6px 0 0;color:#fff;font-size:22px;">📱 알뜰폰 대란 스캐너</h1>
          <p style="margin:6px 0 0;color:#8899aa;font-size:13px;">{date} 기준</p>
        </td>
      </tr>

      <!-- 필터 배지 -->
      <tr>
        <td style="padding:20px 32px 0;background:#fff;">
          <p style="margin:0 0 10px;font-size:12px;color:#666;font-weight:600;">적용 중인 철벽 조건</p>
          {badges}
        </td>
      </tr>

      <!-- 본문 -->
      <tr>
        <td style="padding:24px 32px 32px;">
          <div style="border-left:4px solid #f0a500;padding-left:16px;margin-bottom:20px;">
            <p style="margin:0;font-size:12px;color:#999;">Gemini AI가 최신 요금제 정보를 분석한 결과입니다.</p>
          </div>
          {body}
        </td>
      </tr>

      <!-- 푸터 -->
      <tr>
        <td style="background:#f8f9fb;padding:16px 32px;border-top:1px solid #eee;">
          <p style="margin:0;font-size:11px;color:#aaa;text-align:center;">
            GitHub Actions + Gemini API로 자동 생성 •
            <a href="https://www.moyoplan.com" style="color:#aaa;">모요에서 직접 확인하기</a>
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>

<style>
  .plan {{
    background:#f8f9fb;border-radius:10px;padding:20px 24px;
    margin-bottom:20px;border:1px solid #e8eaf0;
  }}
  .plan h2 {{ margin:0 0 12px;font-size:17px;color:#1a1a2e; }}
  .plan ul {{ margin:0 0 14px;padding-left:18px;font-size:14px;line-height:1.9;color:#333; }}
  .review {{
    background:#fff8e8;border-radius:8px;padding:14px 16px;
    font-size:13px;line-height:1.8;color:#444;border-left:3px solid #f0a500;
  }}
  .none {{ font-size:16px;font-weight:700;color:#e53935;padding:16px 0 8px; }}
  .fail-reason {{
    background:#fff3f3;border-left:3px solid #e53935;
    padding:10px 14px;border-radius:0 8px 8px 0;
    font-size:13px;color:#c62828;margin-top:10px;
  }}
</style>
</body>
</html>
"""

BADGES = [
    ("5G 망", "#1565c0"),
    ("15GB+", "#2e7d32"),
    ("3Mbps 무제한", "#6a1b9a"),
    ("통화 무제한", "#e65100"),
    ("평생 고정", "#c62828"),
    ("월 3만원 이하", "#00695c"),
]

def make_badges() -> str:
    spans = [
        f'<span style="display:inline-block;background:{color};color:#fff;'
        f'font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;margin:2px;">'
        f'{label}</span>'
        for label, color in BADGES
    ]
    return " ".join(spans)


# ── Gemini API 호출 ───────────────────────────────────────
def get_briefing() -> str:
    api_key = os.environ["GEMINI_API_KEY"]
    url = f"{GEMINI_API_URL}?key={api_key}"

    payload = json.dumps({
        "contents": [{"parts": [{"text": PROMPT}]}],
        "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.3},
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as res:
            result = json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print("오류 코드:", e.code)
        print("오류 내용:", e.read().decode())
        raise
      
    return result["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── 이메일 전송 ───────────────────────────────────────────
def send_email(body_html: str) -> None:
    gmail  = os.environ["GMAIL_ADDRESS"]
    app_pw = os.environ["GMAIL_APP_PASSWORD"]
    today  = datetime.now(KST).strftime("%Y년 %m월 %d일")

    full_html = HTML_TEMPLATE.format(
        date=today,
        badges=make_badges(),
        body=body_html,
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[알뜰폰 비서] {today} 브리핑"
    msg["From"]    = f"알뜰폰 비서 <{gmail}>"
    msg["To"]      = gmail
    msg.attach(MIMEText(full_html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail, app_pw)
        server.sendmail(gmail, gmail, msg.as_string())
        print("✅ 이메일 전송 완료")


# ── 메인 ─────────────────────────────────────────────────
def main():
    print(f"🔍 브리핑 생성 시작 — {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")
    briefing_html = get_briefing()
    print("── 브리핑 미리보기 ──")
    print(briefing_html[:300], "...")
    print("────────────────────")
    send_email(briefing_html)


if __name__ == "__main__":
    main()
