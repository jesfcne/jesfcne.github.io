-- 노트 끝에 정정 제보 안내를 붙인다.
--
-- 댓글(giscus)은 GitHub 계정이 있어야 쓸 수 있다. 이 사이트의 독자는
-- 연구자·공무원·기자처럼 계정이 없는 쪽이 더 많을 수 있는데, 정작 이 사이트는
-- "내 주장이 틀렸다면 알려달라"를 전면에 걸고 있다. 반박하려는 사람이
-- 계정 만들기에서 막히면 취지가 무너지므로 계정 없이 쓸 수 있는 통로를 둔다.
--
-- status 가 있는 문서(=노트)에만 붙인다. 필터는 사이트 전체에 걸리므로
-- 랜딩이나 소개 페이지에 새지 않도록 여기서 걸러야 한다.

local EMAIL = "jesfcne+notes@gmail.com"

-- UTF-8 문자열을 바이트 단위로 퍼센트 인코딩한다. mailto 제목에 한글을 넣으려면
-- 필요하다. 인코딩하지 않으면 메일 클라이언트마다 다르게 깨진다.
local function urlencode(s)
  return (s:gsub("[^%w%-%._~]", function(c)
    return string.format("%%%02X", string.byte(c))
  end))
end

local function escape(s)
  return s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;"):gsub('"', "&quot;")
end

function Pandoc(doc)
  if doc.meta.status == nil then
    return nil
  end

  local title = doc.meta.title and pandoc.utils.stringify(doc.meta.title) or ""
  local subject = urlencode("[환경 데이터 노트] " .. title)

  local html = string.format(
    '<aside class="note-correction">'
      .. "<p>사실관계 오류나 다른 해석을 발견하셨다면 알려 주세요. "
      .. "아래 댓글은 GitHub 계정이 있어야 쓸 수 있습니다. "
      .. '계정이 없다면 <a href="mailto:%s?subject=%s">%s</a> 로 주셔도 됩니다.</p>'
      .. "</aside>",
    escape(EMAIL),
    subject,
    escape(EMAIL)
  )

  table.insert(doc.blocks, pandoc.RawBlock("html", html))
  return doc
end
