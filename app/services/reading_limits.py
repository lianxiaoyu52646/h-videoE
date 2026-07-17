"""阅读模块容量限制 — 支持超长篇全集"""

# 单文件上传上限（100MB，足够 Gutenberg 超大 txt）
MAX_UPLOAD_BYTES = 100 * 1024 * 1024

# 正文上限（约 500 万词量级；Gutenberg 最大单书远低于此）
MAX_CONTENT_CHARS = 50_000_000

# 入库时分批写入段落，避免一次性占用过多内存
BLOCK_INSERT_BATCH = 500

# 超过此段数时导入阶段跳过同步 FTS，改为首次搜索时后台补建
DEFER_FTS_BLOCK_THRESHOLD = 3000

# 章节平衡：避免「一章 1 段」或「一章 800 段」
MIN_CHAPTER_BLOCKS = 8
MAX_CHAPTER_BLOCKS = 120

# 翻译 ETA：每段平均耗时（秒），用于冷启动估算
DEFAULT_SEC_PER_BLOCK = 0.45
