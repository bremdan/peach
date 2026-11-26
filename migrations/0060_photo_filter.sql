-- 写真筛选：每位参考对象的向量身份证、筛选任务与筛选结果。只新增表，不改既有表。
--
-- 参考对象的向量来自本地 InsightFace buffalo_l（SCRFD + ArcFace，512 维），以 float32
-- 小端 blob 存放；参考照片副本落在 Peach 数据目录的专用子目录，`storage_subdir` 存相对名。
-- 筛选任务与结果在本步只落结构，打分逻辑留给后续步骤。

CREATE TABLE photo_filter_reference(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    embedding BLOB,
    valid_face_count INTEGER NOT NULL DEFAULT 0 CHECK(valid_face_count >= 0),
    status TEXT NOT NULL CHECK(status IN ('ready', 'failed')),
    failure_reason TEXT NOT NULL DEFAULT '',
    storage_subdir TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL DEFAULT ''
);

CREATE TABLE photo_filter_task(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    root_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    processed_count INTEGER NOT NULL DEFAULT 0 CHECK(processed_count >= 0),
    total_count INTEGER NOT NULL DEFAULT 0 CHECK(total_count >= 0),
    hit_threshold REAL NOT NULL DEFAULT 0.50,
    taste_threshold REAL NOT NULL DEFAULT 0.30
);

CREATE TABLE photo_filter_result(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    task_id INTEGER NOT NULL REFERENCES photo_filter_task(id) ON DELETE CASCADE,
    album_path TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    top_reference_id INTEGER REFERENCES photo_filter_reference(id) ON DELETE SET NULL,
    valid_image_count INTEGER NOT NULL DEFAULT 0 CHECK(valid_image_count >= 0),
    total_image_count INTEGER NOT NULL DEFAULT 0 CHECK(total_image_count >= 0),
    protagonist_cluster_ratio REAL NOT NULL DEFAULT 0,
    tier_label TEXT NOT NULL DEFAULT '',
    representative_face_path TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_photo_filter_result_task ON photo_filter_result(task_id);
CREATE INDEX idx_photo_filter_result_top_reference
ON photo_filter_result(top_reference_id) WHERE top_reference_id IS NOT NULL;

INSERT INTO ledger_revision(tbl) VALUES
    ('photo_filter_reference'), ('photo_filter_task'), ('photo_filter_result');

CREATE TRIGGER rev_photo_filter_reference_insert AFTER INSERT ON photo_filter_reference BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='photo_filter_reference';
END;
CREATE TRIGGER rev_photo_filter_reference_update AFTER UPDATE ON photo_filter_reference BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='photo_filter_reference';
END;
CREATE TRIGGER rev_photo_filter_reference_delete AFTER DELETE ON photo_filter_reference BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='photo_filter_reference';
END;

CREATE TRIGGER rev_photo_filter_task_insert AFTER INSERT ON photo_filter_task BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='photo_filter_task';
END;
CREATE TRIGGER rev_photo_filter_task_update AFTER UPDATE ON photo_filter_task BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='photo_filter_task';
END;
CREATE TRIGGER rev_photo_filter_task_delete AFTER DELETE ON photo_filter_task BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='photo_filter_task';
END;

CREATE TRIGGER rev_photo_filter_result_insert AFTER INSERT ON photo_filter_result BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='photo_filter_result';
END;
CREATE TRIGGER rev_photo_filter_result_update AFTER UPDATE ON photo_filter_result BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='photo_filter_result';
END;
CREATE TRIGGER rev_photo_filter_result_delete AFTER DELETE ON photo_filter_result BEGIN
    UPDATE ledger_revision SET n=n+1 WHERE tbl='photo_filter_result';
END;

-- 运行时连接不依赖 PRAGMA foreign_keys；删除任务时由触发器收齐结果。
CREATE TRIGGER photo_filter_task_delete_results AFTER DELETE ON photo_filter_task BEGIN
    DELETE FROM photo_filter_result WHERE task_id=OLD.id;
END;
-- 删参考对象时，历史结果仍保留，只把「最像谁」置空。
CREATE TRIGGER photo_filter_reference_clear_results AFTER DELETE ON photo_filter_reference BEGIN
    UPDATE photo_filter_result SET top_reference_id=NULL WHERE top_reference_id=OLD.id;
END;
