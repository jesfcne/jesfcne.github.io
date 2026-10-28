-- 각 호 제목 위에 "2026-W43 · 10월 19일 – 10월 25일" 같은 부제를 만든다.
--
-- 호수와 기간은 프론트매터의 issue, period 에서 가져온다. 사람이나 에이전트가
-- 부제를 손으로 쓰면 형식이 호마다 달라지므로 여기서 한 가지 형식으로 찍는다.
-- 목록 페이지도 이 부제(subtitle)를 그대로 보여 준다.
--
-- issue 가 없는 문서(랜딩, 소개)나 subtitle 을 직접 쓴 문서는 건드리지 않는다.

local function korean_date(iso)
  local _, m, d = iso:match("^(%d%d%d%d)-(%d%d)-(%d%d)$")
  if not m then
    return iso
  end
  return string.format("%d월 %d일", tonumber(m), tonumber(d))
end

function Meta(meta)
  if meta.issue == nil or meta.subtitle ~= nil then
    return nil
  end

  local issue = pandoc.utils.stringify(meta.issue)
  local text = issue

  if meta.period ~= nil and meta.period.start ~= nil and meta.period["end"] ~= nil then
    local s = korean_date(pandoc.utils.stringify(meta.period.start))
    local e = korean_date(pandoc.utils.stringify(meta.period["end"]))
    text = string.format("%s · %s – %s", issue, s, e)
  end

  meta.subtitle = pandoc.MetaInlines({ pandoc.Str(text) })
  return meta
end
