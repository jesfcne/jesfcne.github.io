-- 각 호 끝에 정정 제보 안내를 붙인다.
--
-- 댓글(giscus)은 GitHub 계정이 있어야 쓸 수 있다. 이 뉴스레터의 독자는
-- 연구자·공무원·기자처럼 계정이 없는 쪽이 더 많을 수 있는데, 정정 제보가
-- 계정 만들기에서 막히면 안 되므로 계정 없이 쓸 수 있는 통로를 둔다.
--
-- issue 가 있는 문서(=각 호)에만 붙인다. 필터는 사이트 전체에 걸리므로
-- 랜딩이나 소개 페이지에 새지 않도록 여기서 걸러야 한다.

-- Gmail 플러스 별칭. 메일은 그대로 받은편지함에 도착하지만, to: 로 필터를
-- 걸 수 있고 스팸이 감당 안 되면 이 별칭만 버리면 된다. 본 주소는 그대로 쓴다.
-- 봇이 +notes 를 떼어 본 주소를 추측할 수는 있다. 다만 본 주소는 커밋 이력에
-- 이미 공개되어 있으므로 추가로 잃는 것은 없고 격리 이점만 남는다.
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
  if doc.meta.issue == nil then
    return nil
  end

  local title = doc.meta.title and pandoc.utils.stringify(doc.meta.title) or ""
  local subject = urlencode("[기후·환경 주간 브리핑] " .. title)

  local html = string.format(
    '<aside class="note-correction">'
      .. "<p>사실관계 오류를 발견하셨다면 알려 주세요. "
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
