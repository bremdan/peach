"""写真筛选写进账本的状态原因。

单独成文件是为了按仓库约定把用户能看到的中文留在内容数据里（`check_backend_copy` 的
`CONTENT_FILES`），逻辑模块只引用常量。
"""

INSUFFICIENT_FACES = "有效脸不足（{count} 张，需 ≥{needed}）"
