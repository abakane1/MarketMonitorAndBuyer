-- =====================================================
-- MarketMonitorAndBuyer v4.1 情报系统数据库迁移脚本
-- =====================================================
-- 执行时间: 2026-03-14
-- 目标数据库: stock_data/intel_hub.db
-- 备份建议: 执行前请先备份数据库

-- -----------------------------------------------------
-- Phase 1: 新增冷热分离字段
-- -----------------------------------------------------

-- 添加归档标记字段
ALTER TABLE intelligence ADD COLUMN is_archived BOOLEAN DEFAULT 0;

-- 添加摘要字段(用于压缩存储)
ALTER TABLE intelligence ADD COLUMN summary TEXT;

-- 添加置信度字段
ALTER TABLE intelligence ADD COLUMN confidence REAL;

-- 添加情感标签字段 (bullish/bearish/neutral)
ALTER TABLE intelligence ADD COLUMN sentiment TEXT DEFAULT 'neutral';

-- -----------------------------------------------------
-- Phase 2: 创建情报-ETF关联表
-- -----------------------------------------------------

CREATE TABLE IF NOT EXISTS intelligence_stocks (
    intelligence_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    confidence REAL DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (intelligence_id, symbol),
    FOREIGN KEY (intelligence_id) REFERENCES intelligence(id) ON DELETE CASCADE
);

-- 创建索引加速查询
CREATE INDEX idx_intel_stocks_symbol ON intelligence_stocks(symbol);
CREATE INDEX idx_intel_stocks_intel_id ON intelligence_stocks(intelligence_id);

-- -----------------------------------------------------
-- Phase 3: 创建ETF关键词配置表
-- -----------------------------------------------------

CREATE TABLE IF NOT EXISTS etf_keywords (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    keywords TEXT,  -- JSON数组格式
    tags TEXT,      -- JSON数组格式
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认ETF配置
INSERT OR IGNORE INTO etf_keywords (symbol, name, keywords, tags) VALUES
('588200', '科创芯片ETF（嘉实）', 
 '["中芯国际", "海光信息", "寒武纪", "澜起科技", "中微公司", "芯片", "半导体", "科创板"]', 
 '["芯片", "AI", "国产替代"]'),

('588710', '科创半导体设备ETF（华泰柏瑞）', 
 '["拓荆科技", "华海清科", "沪硅产业", "中微公司", "半导体设备", "光刻机"]', 
 '["半导体设备", "国产替代"]'),

('588750', '科创芯片ETF（汇添富）', 
 '["中芯国际", "海光信息", "寒武纪", "澜起科技", "芯片", "半导体"]', 
 '["芯片", "科创板"]');

-- -----------------------------------------------------
-- Phase 4: 创建索引优化查询
-- -----------------------------------------------------

-- 加速活跃情报查询
CREATE INDEX idx_intel_active ON intelligence(is_active, is_archived, created_at);

-- 加速优先级排序查询
CREATE INDEX idx_intel_priority ON intelligence(priority, created_at DESC);

-- 加速ETF代码查询
CREATE INDEX idx_intel_symbol ON intelligence(symbol, is_archived, created_at);

-- -----------------------------------------------------
-- Phase 5: 数据迁移(如有旧数据)
-- -----------------------------------------------------

-- 标记6个月前的情报为已归档(可选)
-- UPDATE intelligence 
-- SET is_archived = 1 
-- WHERE created_at < datetime('now', '-6 months');

-- -----------------------------------------------------
-- 验证迁移结果
-- -----------------------------------------------------

-- 检查表结构
.schema intelligence
.schema intelligence_stocks
.schema etf_keywords

-- 检查数据
SELECT COUNT(*) as total_intel FROM intelligence;
SELECT COUNT(*) as archived_intel FROM intelligence WHERE is_archived = 1;
SELECT * FROM etf_keywords;

-- =====================================================
-- 迁移完成
-- =====================================================
