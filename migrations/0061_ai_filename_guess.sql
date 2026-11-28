-- AI 猜文件名：猜测留痕、复核状态与作品挂接。只新增表，不改既有表结构。
--
-- 本步只落数据层，不接采集管线、不调 API、不做界面。猜测记录的十项内容分别是：
-- 作品（asset_id）、文件名快照、服务商预设名、model、提示词版本、原始返回、解析结果、
-- confidence、路由结果与时间。原始返回与解析结果按文本存放，JSON 由调用方序列化。
--
-- 作品只通过 `ai_filename_guess_asset` 挂接自动入库标记与复核状态，不给 `asset` 加列：
-- 「只加不改」既包括不删旧列，也包括不改变既有表的结构。

CREATE TABLE ai_filename_guess(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    raw_response TEXT NOT NULL DEFAULT '',
    parsed_result TEXT NOT NULL DEFAULT '',
    confidence REAL,
    route TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX idx_ai_filename_guess_asset
ON ai_filename_guess(asset_id, created_at);

-- 每条猜测最多一条复核状态。状态取英文 id（ADR-0162），界面译文留给复核队列页。
CREATE TABLE ai_filename_guess_review(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guess_id INTEGER NOT NULL UNIQUE REFERENCES ai_filename_guess(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN (
        'pending', 'accepted', 'modified_accepted', 'rejected', 'rolled_back')),
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_ai_filename_guess_review_status
ON ai_filename_guess_review(status);

CREATE TABLE ai_filename_guess_asset(
    asset_id INTEGER PRIMARY KEY REFERENCES asset(id) ON DELETE CASCADE,
    auto_ingest INTEGER NOT NULL DEFAULT 0 CHECK(auto_ingest IN (0, 1)),
    review_id INTEGER REFERENCES ai_filename_guess_review(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_ai_filename_guess_asset_review
ON ai_filename_guess_asset(review_id) WHERE review_id IS NOT NULL;

INSERT INTO ledger_revision(tbl) VALUES
    ('ai_filename_guess'), ('ai_filename_guess_review'), ('ai_filename_guess_asset');

CREATE TRIGGER rev_ai_filename_guess_insert AFTER INSERT ON ai_filename_guess BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='ai_filename_guess';
END;
CREATE TRIGGER rev_ai_filename_guess_update AFTER UPDATE ON ai_filename_guess BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='ai_filename_guess';
END;
CREATE TRIGGER rev_ai_filename_guess_delete AFTER DELETE ON ai_filename_guess BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='ai_filename_guess';
END;

CREATE TRIGGER rev_ai_filename_guess_review_insert AFTER INSERT ON ai_filename_guess_review BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='ai_filename_guess_review';
END;
CREATE TRIGGER rev_ai_filename_guess_review_update AFTER UPDATE ON ai_filename_guess_review BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='ai_filename_guess_review';
END;
CREATE TRIGGER rev_ai_filename_guess_review_delete AFTER DELETE ON ai_filename_guess_review BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='ai_filename_guess_review';
END;

CREATE TRIGGER rev_ai_filename_guess_asset_insert AFTER INSERT ON ai_filename_guess_asset BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='ai_filename_guess_asset';
END;
CREATE TRIGGER rev_ai_filename_guess_asset_update AFTER UPDATE ON ai_filename_guess_asset BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='ai_filename_guess_asset';
END;
CREATE TRIGGER rev_ai_filename_guess_asset_delete AFTER DELETE ON ai_filename_guess_asset BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='ai_filename_guess_asset';
END;

-- 运行时连接不依赖 PRAGMA foreign_keys；删除作品、猜测或复核行时由触发器收齐挂接行。
CREATE TRIGGER ai_filename_guess_asset_delete_guesses AFTER DELETE ON asset BEGIN
    DELETE FROM ai_filename_guess WHERE asset_id=OLD.id;
    DELETE FROM ai_filename_guess_asset WHERE asset_id=OLD.id;
END;

CREATE TRIGGER ai_filename_guess_delete_reviews AFTER DELETE ON ai_filename_guess BEGIN
    DELETE FROM ai_filename_guess_review WHERE guess_id=OLD.id;
END;

CREATE TRIGGER ai_filename_guess_review_clear_asset AFTER DELETE ON ai_filename_guess_review BEGIN
    UPDATE ai_filename_guess_asset SET review_id=NULL WHERE review_id=OLD.id;
END;
