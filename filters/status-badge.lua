-- 노트 프론트매터의 status 를 본문 맨 위 배지로 보여준다.
--
-- status 는 이 사이트의 핵심 개념(씨앗 -> 발행 -> 감시)인데 프론트매터에만
-- 있어서 정작 노트를 열어 보면 그 노트가 어느 단계인지 알 수 없었다.
-- 초고를 확정된 주장으로 오해하지 않으려면 화면에 드러나야 한다.

local LABELS = {
  seed = "씨앗",
  probing = "탐색 중",
  draft = "초고",
  published = "발행",
  watching = "감시 중",
  retired = "폐기",
}

local NOTES = {
  seed = "질문만 있고 자료를 아직 보지 않았습니다.",
  probing = "자료를 살펴보는 중이며 결론이 없습니다.",
  draft = "초고입니다. 주장이 아직 확정되지 않았습니다.",
  published = "주장과 반증 조건이 확정됐습니다.",
  watching = "발행됐고 반증 조건을 계속 지켜보는 중입니다.",
  retired = "새 자료가 주장을 뒤집었습니다. 본문 끝에 무엇이 왜 틀렸는지 적혀 있습니다.",
}

local function escape(s)
  return s:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
end

function Pandoc(doc)
  if doc.meta.status == nil then
    return nil
  end

  local key = pandoc.utils.stringify(doc.meta.status)
  local label = LABELS[key]
  if label == nil then
    return nil
  end

  local html = string.format(
    '<div class="note-status status-%s">'
      .. '<span class="note-status-dot" aria-hidden="true"></span>'
      .. '<span class="note-status-label">%s</span>'
      .. '<span class="note-status-note">%s</span>'
      .. "</div>",
    escape(key),
    escape(label),
    escape(NOTES[key] or "")
  )

  table.insert(doc.blocks, 1, pandoc.RawBlock("html", html))
  return doc
end
