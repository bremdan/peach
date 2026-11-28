"""写真筛选写进账本的状态原因。

单独成文件是为了按仓库约定把用户能看到的中文留在内容数据里（`check_backend_copy` 的
`CONTENT_FILES`），逻辑模块只引用常量。
"""

INSUFFICIENT_FACES = "有效脸不足（{count} 张，需 ≥{needed}）"

#: 图集得分分层：写进 `photo_filter_result.tier_label`，也供下一步界面直接显示。
TIER_HIT = "命中"
TIER_SUSPECTED = "疑似命中·待确认"
TIER_TASTE = "口味相似"
TIER_MISS = "未命中"
TIER_INSUFFICIENT = "信号不足"
#: ZIP 图集无法读取时写进 `tier_label` 的前缀，后面接具体原因。
TIER_READ_FAILED = "读取失败"
#: 图集读取失败的具体原因模板；`name` 是集名，`error` 是底层异常说明。
ALBUM_CORRUPT = "{name} 损坏或不是有效的 ZIP 文件"
ALBUM_ENCRYPTED = "{name} 已加密，无法读取"
ALBUM_UNSUPPORTED_COMPRESSION = "{name} 使用了不支持的压缩方式"
ALBUM_UNREADABLE = "{name} 无法读取：{error}"
#: 主角簇占比不足一半时的加注；附在分层名后面，不改分数。
PROTAGONIST_SPREAD = "主角不集中，可能为多人合集"
