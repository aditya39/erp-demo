# Menampilkan langkah agent dari `claude -p --output-format stream-json --verbose` dengan ringkas.
if .type == "assistant" then
  (.message.content[]? |
    if .type == "text" then "\n[agent] " + .text
    elif .type == "tool_use" then
      "  > " + (.name | sub("^mcp__playwright__"; "browser: ")) + "  "
        + ((.input | tostring) | if length > 140 then .[0:140] + "…" else . end)
    else empty end)
elif .type == "result" then
  "\n== Selesai: \(.num_turns) langkah, \((.duration_ms // 0) / 1000 | floor) detik"
    + (if .is_error then " (ada galat: \(.subtype))" else "" end)
    + (if ((.permission_denials // []) | length) > 0
       then "\n   DITOLAK permission: \(.permission_denials | length) panggilan tool ("
            + ([.permission_denials[] | .tool_name // "?"] | unique | join(", ")) + ")"
       else "" end)
else empty end
