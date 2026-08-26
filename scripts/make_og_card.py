"""링크 공유용 소셜 카드(og:image)를 만든다.

카톡·슬랙·트위터에 주소를 붙이면 뜨는 미리보기 이미지다. 없으면 제목만
덩그러니 나온다. 사이트 도형과 같은 모티프를 써서 인상을 맞춘다.

글꼴은 Windows 기본 맑은 고딕을 쓴다. 이 이미지는 결과물을 커밋해 두므로
다른 환경에서 다시 만들 일은 없다.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = "#fafafa"
HEADING = "#18181b"
BODY = "#3f3f46"
MUTED = "#71717a"
ACCENT = "#0f766e"

FONT_DIR = Path("C:/Windows/Fonts")
BOLD = FONT_DIR / "malgunbd.ttf"
REGULAR = FONT_DIR / "malgun.ttf"

# 사이트 도형과 같은 구성: 위에서부터 시간별·일별·월별·분기별
ROWS = [(13, 3.0, 0.95), (7, 3.6, 0.78), (4, 4.2, 0.62), (2, 4.8, 0.48)]


def blend(hex_color: str, opacity: float, bg: str = BG) -> tuple:
    """PNG에는 알파 대신 배경과 미리 섞은 색을 쓴다."""
    fg = tuple(int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    back = tuple(int(bg[i : i + 2], 16) for i in (1, 3, 5))
    return tuple(round(f * opacity + b * (1 - opacity)) for f, b in zip(fg, back))


def main() -> None:
    if not BOLD.exists():
        raise SystemExit(f"글꼴을 찾을 수 없습니다: {BOLD}")

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    title = ImageFont.truetype(str(BOLD), 68)
    lead = ImageFont.truetype(str(REGULAR), 30)
    small = ImageFont.truetype(str(REGULAR), 24)

    x = 90
    d.text((x, 168), "환경 데이터 노트", font=title, fill=HEADING)
    d.text((x, 286), "국내 공개 환경 데이터를 직접 수집·분석해", font=lead, fill=BODY)
    d.text((x, 332), "얻은 인사이트를 기록합니다.", font=lead, fill=BODY)

    d.line([(x, 412), (x + 56, 412)], fill=ACCENT, width=3)
    d.text((x, 440), "jesfcne.github.io", font=small, fill=MUTED)

    # 오른쪽 도형
    art_x0, art_x1, art_y = 760, 1110, 200
    for n, r, op in ROWS:
        color = blend(ACCENT, op)
        d.line([(art_x0, art_y), (art_x1, art_y)], fill=blend(ACCENT, op * 0.2), width=2)
        step = (art_x1 - art_x0) / (n - 1)
        for i in range(n):
            cx = art_x0 + i * step
            d.ellipse([cx - r * 2, art_y - r * 2, cx + r * 2, art_y + r * 2], fill=color)
        art_y += 76

    out = Path(__file__).resolve().parent.parent / "og-card.png"
    img.save(out, optimize=True)
    print(f"{out.name} 생성: {out.stat().st_size // 1024}KB, {W}x{H}")


if __name__ == "__main__":
    main()
