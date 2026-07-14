-- ============================================================
-- 金融研报智能分析与投资决策辅助系统
-- MySQL 8.0 数据库初始化脚本
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS financial_research
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE financial_research;

-- ============================================================
-- 1. 券商研报表
-- ============================================================
CREATE TABLE IF NOT EXISTS research_reports (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    title           VARCHAR(512)    NOT NULL            COMMENT '研报标题',
    institution     VARCHAR(128)    NOT NULL            COMMENT '发布机构',
    analyst         VARCHAR(64)                         COMMENT '分析师',
    report_date     DATE            NOT NULL            COMMENT '发布日期',
    stock_code      VARCHAR(16)                         COMMENT '股票代码',
    stock_name      VARCHAR(64)                         COMMENT '股票名称',
    industry        VARCHAR(64)                         COMMENT '所属行业',
    report_type     VARCHAR(32)                         COMMENT '研报类型: 深度研究/公司点评/行业研究',
    rating          VARCHAR(16)                         COMMENT '投资评级: 买入/增持/中性/减持/卖出',
    target_price    FLOAT                               COMMENT '目标价',
    current_price   FLOAT                               COMMENT '当前价',
    profit_forecast JSON                                COMMENT '盈利预测 JSON',
    risk_warnings   TEXT                                COMMENT '风险提示',
    core_viewpoint  TEXT                                COMMENT '核心观点摘要',
    full_content    MEDIUMTEXT                          COMMENT '研报全文',
    source_url      VARCHAR(512)                        COMMENT '原文链接',
    sentiment_score FLOAT                               COMMENT '情感得分 -1.0~1.0',
    created_at      DATETIME    DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_report_stock        (stock_code, report_date),
    INDEX idx_report_date         (report_date),
    INDEX idx_report_institution  (institution, report_date),
    INDEX idx_report_industry     (industry, report_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='券商研报';


-- ============================================================
-- 2. 财经新闻表
-- ============================================================
CREATE TABLE IF NOT EXISTS financial_news (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    title           VARCHAR(512)    NOT NULL            COMMENT '新闻标题',
    source          VARCHAR(128)    NOT NULL            COMMENT '来源',
    author          VARCHAR(64)                         COMMENT '作者',
    publish_time    DATETIME        NOT NULL            COMMENT '发布时间',
    url             VARCHAR(512)                        COMMENT '原文链接',
    content         MEDIUMTEXT                          COMMENT '正文内容',
    summary         TEXT                                COMMENT 'AI摘要',
    tags            JSON                                COMMENT '标签 JSON 数组',
    related_stocks  JSON                                COMMENT '关联股票',
    sentiment_label VARCHAR(16)                         COMMENT '情感标签: positive/neutral/negative',
    sentiment_score FLOAT                               COMMENT '情感得分',
    created_at      DATETIME    DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_news_time       (publish_time),
    INDEX idx_news_sentiment  (sentiment_label, publish_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='财经新闻';


-- ============================================================
-- 3. 公司公告表
-- ============================================================
CREATE TABLE IF NOT EXISTS company_announcements (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    stock_code      VARCHAR(16)     NOT NULL            COMMENT '股票代码',
    stock_name      VARCHAR(64)                         COMMENT '股票名称',
    title           VARCHAR(512)    NOT NULL            COMMENT '公告标题',
    announce_date   DATE            NOT NULL            COMMENT '公告日期',
    announce_type   VARCHAR(32)                         COMMENT '公告类型',
    content         MEDIUMTEXT                          COMMENT '公告全文',
    summary         TEXT                                COMMENT 'AI摘要',
    key_points      JSON                                COMMENT '关键要点',
    created_at      DATETIME    DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_announce_stock (stock_code, announce_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='公司公告';


-- ============================================================
-- 4. 社交舆情表
-- ============================================================
CREATE TABLE IF NOT EXISTS social_sentiment (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    stock_code      VARCHAR(16)                         COMMENT '股票代码',
    stock_name      VARCHAR(64)                         COMMENT '股票名称',
    platform        VARCHAR(32)     NOT NULL            COMMENT '平台: 微博/雪球/东方财富/同花顺',
    content         TEXT                                COMMENT '舆情内容',
    author          VARCHAR(64)                         COMMENT '作者',
    post_time       DATETIME        NOT NULL            COMMENT '发布时间',
    sentiment_label VARCHAR(16)                         COMMENT '情感标签',
    sentiment_score FLOAT                               COMMENT '情感得分 -1.0~1.0',
    hot_index       INT             DEFAULT 0           COMMENT '热度指数',
    created_at      DATETIME    DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_social_stock    (stock_code, post_time),
    INDEX idx_social_platform (platform, hot_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='社交舆情';


-- ============================================================
-- 5. 知识库文档表
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    title           VARCHAR(256)    NOT NULL            COMMENT '文档标题',
    doc_type        VARCHAR(32)                         COMMENT '文档类型: 研报/新闻/公告/自定义',
    content         MEDIUMTEXT                          COMMENT '文档内容',
    vector_id       VARCHAR(128)                        COMMENT '向量存储ID',
    tags            JSON                                COMMENT '标签',
    related_stocks  JSON                                COMMENT '关联股票',
    file_path       VARCHAR(512)                        COMMENT '文件路径',
    status          VARCHAR(16)     DEFAULT 'active'    COMMENT '状态: active/archived',
    created_at      DATETIME    DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_kb_type   (doc_type),
    INDEX idx_kb_status (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='知识库文档';


-- ============================================================
-- 6. 投资问答历史表
-- ============================================================
CREATE TABLE IF NOT EXISTS investment_qa (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(64)     NOT NULL            COMMENT '会话ID',
    question        TEXT            NOT NULL            COMMENT '用户问题',
    answer          MEDIUMTEXT                          COMMENT '系统回答',
    sources         JSON                                COMMENT '引用来源',
    related_stocks  JSON                                COMMENT '相关股票',
    feedback        VARCHAR(16)                         COMMENT '用户反馈: 有用/无用',
    created_at      DATETIME    DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_qa_session (session_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='投资问答历史';


-- ============================================================
-- 7. 内容模板表
-- ============================================================
CREATE TABLE IF NOT EXISTS content_templates (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(128)    NOT NULL            COMMENT '模板名称',
    category        VARCHAR(32)                         COMMENT '分类: 研报摘要/投资建议/行业分析/自定义',
    prompt_template TEXT                                COMMENT '提示词模板',
    output_format   JSON                                COMMENT '输出格式定义',
    created_at      DATETIME    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='内容模板';


-- ============================================================
-- 初始数据: 预置内容模板
-- ============================================================
INSERT INTO content_templates (name, category, prompt_template) VALUES
(
    '深度研报摘要模板',
    '研报摘要',
    '请基于以下数据生成一份专业的{stock_name}（{stock_code}）研报摘要。\n\n要求：\n1. 公司概况与近期经营亮点\n2. 财务数据核心指标（营收、净利润、毛利率）\n3. 机构评级分布与目标价区间\n4. 核心投资逻辑\n5. 主要风险提示\n\n请使用专业的金融分析语言，关键数据用数字呈现。'
),
(
    '投资建议书模板',
    '投资建议',
    '请基于以下数据生成一份{stock_name}（{stock_code}）的投资建议书。\n\n要求：\n1. 投资概述与核心逻辑\n2. 公司基本面分析\n3. 估值分析与目标价位\n4. 风险收益评估\n5. 持仓建议与操作策略\n\n末尾请附上风险提示和免责声明。'
),
(
    '行业分析报告模板',
    '行业分析',
    '请基于以下数据生成一份行业分析报告。\n\n要求：\n1. 行业概况与发展阶段\n2. 竞争格局与主要玩家\n3. 产业链分析\n4. 政策环境与监管动态\n5. 投资机会与风险\n\n数据要详实，分析要有深度。'
),
(
    '每日市场简报模板',
    '市场简报',
    '请生成一份每日市场简报。\n\n要求：\n1. 大盘综述（主要指数表现）\n2. 热点板块与领涨/领跌个股\n3. 资金流向（北向资金、主力资金）\n4. 重要公告与事件提醒\n5. 次日关注要点\n\n简洁明了，控制在一屏内可读完。'
);
