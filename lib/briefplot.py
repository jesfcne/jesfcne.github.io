"""뉴스레터 차트 공통 스타일.

모든 호의 차트가 같은 색, 글꼴, 축, 툴팁 규칙을 따르도록 여기서만 정한다.
각 호에서는 데이터와 문구만 넘긴다.

라이트/다크 대응은 Quarto 의 renderings 기능을 쓴다. 코드 셀에
`#| renderings: [light, dark]` 를 달고 라이트 그림, 다크 그림 순서로 출력하면
사이트 테마 토글에 맞춰 둘 중 하나만 보인다. `show()` 가 그 순서를 지켜 준다.

    from briefplot import line, show
    show(lambda theme: line(df, "year", "value", unit="ppm", theme=theme))

색은 dataviz 기준 팔레트에서 가져왔고, 라이트/다크 각각 따로 고른 단계다.
(파랑-빨강 발산쌍, 1번 계열색 파랑)
"""

from __future__ import annotations

from typing import Callable

import plotly.graph_objects as go

FONT = '"Pretendard Variable", Pretendard, -apple-system, "Segoe UI", "Malgun Gothic", sans-serif'

THEMES = {
    "light": {
        "text": "#3f3f46",
        "muted": "#71717a",
        "grid": "#e4e4e7",
        "axis": "#a1a1aa",
        "baseline": "#71717a",
        "series": "#2a78d6",
        "series_soft": "#86b6ef",
        "warm": "#e34948",
        "cool": "#2a78d6",
        "hover_bg": "#ffffff",
        "hover_border": "#e4e4e7",
    },
    "dark": {
        "text": "#d4d4d8",
        "muted": "#a1a1aa",
        "grid": "#27272a",
        "axis": "#52525b",
        "baseline": "#a1a1aa",
        "series": "#3987e5",
        "series_soft": "#1c5cab",
        "warm": "#e66767",
        "cool": "#3987e5",
        "hover_bg": "#18181b",
        "hover_border": "#3f3f46",
    },
}

CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False}


def _layout(fig: go.Figure, t: dict, *, unit: str, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=16, t=28, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=13, color=t["text"]),
        showlegend=False,
        hovermode="x",
        hoverlabel=dict(
            bgcolor=t["hover_bg"],
            bordercolor=t["hover_border"],
            font=dict(family=FONT, size=13, color=t["text"]),
        ),
    )
    # 단위는 축 제목 대신 축 위 왼쪽에 작게 둔다. 세로 축 제목은 한글이 돌아가 읽기 어렵다.
    # update_layout(annotations=...) 로 넣으면 앞서 붙인 주석이 지워지므로 add_annotation 을 쓴다.
    if unit:
        fig.add_annotation(
            text=unit, xref="paper", yref="paper", x=0, y=1,
            xanchor="left", yanchor="bottom", yshift=6, showarrow=False,
            font=dict(size=12, color=t["muted"]),
        )
    fig.update_xaxes(
        showgrid=False,
        linecolor=t["axis"],
        ticks="outside",
        tickcolor=t["axis"],
        tickfont=dict(color=t["muted"]),
        showspikes=True,
        spikemode="across",
        spikethickness=1,
        spikedash="solid",
        spikecolor=t["axis"],
        spikesnap="cursor",
    )
    fig.update_yaxes(
        gridcolor=t["grid"],
        zeroline=False,
        tickfont=dict(color=t["muted"]),
        ticklabelstandoff=6,
    )
    return fig


def line(
    df,
    x: str,
    y: str,
    *,
    unit: str = "",
    value_format: str = ".1f",
    label_last: bool = True,
    baseline: float | None = None,
    baseline_label: str = "",
    height: int = 340,
    theme: str = "light",
) -> go.Figure:
    """장기 시계열 한 개. 마지막 값을 강조하고 직접 표기한다."""
    t = THEMES[theme]
    fig = go.Figure(
        go.Scatter(
            x=df[x],
            y=df[y],
            mode="lines",
            line=dict(color=t["series"], width=2),
            hovertemplate=f"%{{x}}<br><b>%{{y:{value_format}}}</b> {unit}<extra></extra>",
        )
    )
    if baseline is not None:
        fig.add_hline(y=baseline, line=dict(color=t["baseline"], width=1, dash="dot"))
        if baseline_label:
            fig.add_annotation(
                x=0, xref="paper", y=baseline, text=baseline_label, showarrow=False,
                xanchor="left", yanchor="bottom", font=dict(size=12, color=t["muted"]),
            )
    if label_last and len(df):
        last = df.iloc[-1]
        fig.add_trace(
            go.Scatter(
                x=[last[x]], y=[last[y]], mode="markers",
                marker=dict(size=8, color=t["series"], line=dict(width=2, color=t["hover_bg"])),
                hoverinfo="skip",
            )
        )
        fig.add_annotation(
            x=last[x], y=last[y], text=f"{last[y]:{value_format}}",
            showarrow=False, xanchor="left", xshift=8,
            font=dict(size=13, color=t["text"]),
        )
    fig = _layout(fig, t, unit=unit, height=height)
    if label_last:
        # 마지막 값 표기가 그림 밖으로 잘리지 않게 오른쪽 여백을 늘린다.
        fig.update_layout(margin=dict(r=56))
    return fig


def anomaly_bars(
    df,
    x: str,
    y: str,
    *,
    unit: str = "",
    value_format: str = "+.2f",
    height: int = 340,
    theme: str = "light",
) -> go.Figure:
    """기준값 대비 편차. 0보다 크면 따뜻한 색, 작으면 차가운 색."""
    t = THEMES[theme]
    colors = [t["warm"] if v >= 0 else t["cool"] for v in df[y]]
    fig = go.Figure(
        go.Bar(
            x=df[x],
            y=df[y],
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate=f"%{{x}}<br><b>%{{y:{value_format}}}</b> {unit}<extra></extra>",
        )
    )
    fig.update_layout(bargap=0.15)
    fig.add_hline(y=0, line=dict(color=t["baseline"], width=1))
    return _layout(fig, t, unit=unit, height=height)


def show(make: Callable[[str], go.Figure]) -> None:
    """라이트, 다크 순서로 그림을 출력한다. 셀에 renderings: [light, dark] 가 있어야 한다."""
    for theme in ("light", "dark"):
        make(theme).show(config=CONFIG)
