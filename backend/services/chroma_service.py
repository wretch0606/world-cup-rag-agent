"""
世界杯知识库 — Chroma 向量数据库服务模块
=====================================
负责：BGE Embedding、双 Collection 管理、chunk 写入、
      语义检索（含 metadata 过滤）、query rewrite、reranker 重排序

被调用方：B（LangGraph Agent）
数据来源：C（数据处理模块）提供的结构化世界杯数据

Collection 设计（见开发文档 5.3 节）：
  - world_cup_match_facts：每场比赛的标准化事实文本（精确检索）
  - world_cup_reports：比赛报告、球队回顾等长文本（语义检索/总结）

Embedding 模式（通过 EMBEDDING_MODE 环境变量切换）：
  - "default"（默认）：Chroma 内置 all-MiniLM-L6-v2，无需下载，离线可用
  - "bge"：BAAI/bge-small-zh-v1.5，中文效果好，需网络下载（~24MB）
  切换方法：set EMBEDDING_MODE=bge   （Windows cmd）
          $env:EMBEDDING_MODE="bge"  （PowerShell）
"""

import os
import re
import logging
from typing import Optional

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

# ---------------------------------------------------------------------------
# 配置常量
# ---------------------------------------------------------------------------

CHROMA_DATA_DIR = os.environ.get("CHROMA_DATA_DIR", "./backend/data/chroma_db")

# 数据库路径（C→B 交付的 SQLite，D 仅用于调试增强）
# 正式流程中 B/E 负责 SQLite 查询，D 的 enrich_result() 是可选调试辅助
WORLD_CUP_DB_PATH = os.environ.get("WORLD_CUP_DB_PATH", "")

# 两个 Collection（见文档 5.3 节）
COLLECTION_FACTS = "world_cup_match_facts"    # 比赛事实（精确检索）
COLLECTION_REPORTS = "world_cup_reports"       # 比赛报告/长文本（语义检索）

# Embedding 模式选择
#   "default" = Chroma 内置 ONNX 模型（all-MiniLM-L6-v2，离线可用）
#   "bge"     = BAAI/bge-small-zh-v1.5（中文效果好，需网络下载）
EMBEDDING_MODE = os.environ.get("EMBEDDING_MODE", "default")
COLLECTION_REPORTS = "world_cup_reports"       # 比赛报告/长文本（语义检索）

# Embedding 模式选择
#   "default" = Chroma 内置 ONNX 模型（all-MiniLM-L6-v2，离线可用）
#   "bge"     = BAAI/bge-small-zh-v1.5（中文效果好，需网络下载）
EMBEDDING_MODE = os.environ.get("EMBEDDING_MODE", "default")

# BGE 中文 Embedding 模型（仅在 mode="bge" 时使用）
# 优先使用 ModelScope 本地缓存，其次尝试 HuggingFace
_BGE_MODELSCOPE_PATH = os.path.expanduser(
    "~/.cache/modelscope/models/BAAI--bge-small-zh-v1.5/snapshots/master"
)
EMBEDDING_MODEL_NAME = _BGE_MODELSCOPE_PATH if os.path.isdir(_BGE_MODELSCOPE_PATH) \
    else "BAAI/bge-small-zh-v1.5"

# Reranker 模型（对召回结果精排，仅在 mode="bge" 时可用）
RERANKER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

logger = logging.getLogger("chroma_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)

# ===================================================================
#                   BGE Embedding 函数
# ===================================================================


class BGEEmbeddingFunction(EmbeddingFunction):
    """使用 BGE 模型的自定义 Embedding 函数。

    BGE 模型特点：
    - 中文语义理解远超默认的 all-MiniLM-L6-v2
    - 输入前建议加 "为这个句子生成表示以用于检索相关文章：" 前缀（BGE 官方推荐）
    - 输出需要 normalize（L2 归一化），确保余弦相似度计算准确
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self._model = None  # 延迟加载
        self.model_name = model_name
        # BGE 模型推荐的 query 前缀（增强检索效果）
        self.query_prefix = "为这个句子生成表示以用于检索相关文章："

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"正在加载 BGE 模型: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info(f"BGE 模型加载完成，向量维度: {self._model.get_sentence_embedding_dimension()}")
        return self._model

    def __call__(self, input: Documents) -> Embeddings:
        """Chroma 会调用此方法，传入文本列表，返回向量列表。"""
        model = self._load_model()
        # BGE 推荐：对所有文本（包括文档和查询）使用相同的 encode 方式
        # 注意：这里不加 query_prefix，因为这是对文档侧做 embedding
        embeddings = model.encode(
            input,
            normalize_embeddings=True,  # L2 归一化
            show_progress_bar=False,
        )
        return embeddings.tolist()

    def encode_query(self, query: str) -> list[float]:
        """对查询文本做 embedding（带 query prefix）。

        与文档 embedding 分开处理，确保查询向量和文档向量在语义空间对齐。
        """
        model = self._load_model()
        # BGE 官方推荐：查询侧加 instruction prefix
        embedding = model.encode(
            self.query_prefix + query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()


# 模块级单例
_ef: Optional[BGEEmbeddingFunction] = None


def get_embedding_function():
    """获取 Embedding 函数。

    - "default" 模式：返回 None，Chroma 使用内置的 all-MiniLM-L6-v2（ONNX，离线可用）
    - "bge" 模式：返回 BGEEmbeddingFunction 实例（中文效果好，需网络下载一次）
    """
    global _ef
    if EMBEDDING_MODE == "bge":
        if _ef is None:
            logger.info(f"Embedding 模式: BGE ({EMBEDDING_MODEL_NAME})")
            _ef = BGEEmbeddingFunction()
        return _ef
    else:
        # 使用 Chroma 内置模型（默认）
        if _ef is None:
            logger.info("Embedding 模式: Chroma 内置 (all-MiniLM-L6-v2, ONNX)")
            _ef = None  # None 表示让 Chroma 自己处理
        return None

# ===================================================================
#                   Reranker（精排）
# ===================================================================


class Reranker:
    """使用 BGE Reranker 对召回结果精细排序。

    Reranker 原理（与 Embedding 不同）：
    - Embedding：将问题和文档分别编码为向量，计算余弦相似度（速度快，精度较低）
    - Reranker：将「问题+文档」拼接后一起输入模型做交叉编码（Cross-Encoder），
      直接输出相关性分数（速度慢，精度高）

    使用策略：
    - 第一步：用 Embedding + Chroma 做粗筛（Top-20）
    - 第二步：用 Reranker 对 Top-20 精排（Top-5）

    注意：Reranker 需要下载模型（~1GB），仅在 EMBEDDING_MODE="bge" 且网络可用时生效。
    """

    def __init__(self, model_name: str = RERANKER_MODEL_NAME):
        self._model = None
        self._available = True  # 网络不可用时自动降级
        self.model_name = model_name

    def _load_model(self):
        if self._model is None and self._available:
            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"正在加载 Reranker 模型: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                logger.info("Reranker 模型加载完成")
            except Exception as e:
                logger.warning(f"Reranker 模型加载失败（将跳过多轮精排）: {e}")
                self._available = False
                self._model = None
        return self._model

    @property
    def is_available(self) -> bool:
        """Reranker 是否可用。"""
        return self._available and EMBEDDING_MODE == "bge"

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """对文档列表重排序。

        如果 Reranker 不可用（网络问题/未启用 BGE），返回空列表，
        调用方应 fallback 到原始的 Chroma 排序。

        返回:
            [(原始索引, 相关性分数), ...]  按分数降序排列
        """
        if not documents:
            return []

        if not self.is_available:
            return []  # 不可用时返回空，让调用方 fallback

        model = self._load_model()
        if model is None:
            return []

        # CrossEncoder 输入格式：[(query, doc), (query, doc), ...]
        pairs = [[query, doc] for doc in documents]
        scores = model.predict(pairs, show_progress_bar=False)

        # 按分数降序排序
        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]


_reranker: Optional[Reranker] = None


def get_reranker() -> Reranker:
    """获取 Reranker 单例。"""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def is_reranker_available() -> bool:
    """检查 Reranker 是否可用。"""
    return get_reranker().is_available

# ===================================================================
#                   Chroma 客户端 & Collection 管理
# ===================================================================


_client: Optional[chromadb.PersistentClient] = None


def _get_client() -> chromadb.PersistentClient:
    """获取 Chroma 持久化客户端（单例）。"""
    global _client
    if _client is None:
        os.makedirs(CHROMA_DATA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_DATA_DIR)
        logger.info(f"Chroma 客户端已初始化，数据目录: {CHROMA_DATA_DIR}")
    return _client


def get_facts_collection():
    """获取「比赛事实」collection — 用于精确事实查询。

    存储内容：每场比赛的标准化描述文本
    示例：「2018年俄罗斯世界杯决赛，法国队对阵克罗地亚队，
          90分钟内比分为4:2，法国队获胜。result_type=regulation」
    """
    client = _get_client()
    return client.get_or_create_collection(
        name=COLLECTION_FACTS,
        embedding_function=get_embedding_function(),
        metadata={"description": "世界杯比赛标准化事实文本，用于精确检索"},
    )


def get_reports_collection():
    """获取「比赛报告」collection — 用于总结/分析类查询。

    存储内容：比赛报告、球队回顾、新闻文章的长文本 chunk
    """
    client = _get_client()
    return client.get_or_create_collection(
        name=COLLECTION_REPORTS,
        embedding_function=get_embedding_function(),
        metadata={"description": "世界杯比赛报告和长文本，用于总结和分析"},
    )

# ===================================================================
#                   Query Rewrite（查询改写）
# ===================================================================


def _find_file(filename: str, env_var: Optional[str] = None) -> Optional[str]:
    """通用文件查找：依次搜索多个可能路径。

    优先级：环境变量 > D/ 文件夹 > 项目根 > backend 相对路径
    """
    # 1. 环境变量
    if env_var:
        env_path = os.environ.get(env_var)
        if env_path and os.path.isfile(env_path):
            return env_path

    # 2. 项目根目录下的常见子目录
    project_root = os.path.join(os.path.dirname(__file__), "..", "..")
    candidates = [
        filename,                                                       # 当前目录
        os.path.join(project_root, filename),                           # 项目根
        os.path.join(project_root, "D", filename),                      # D 文件夹（C 交付）
        os.path.join(project_root, "交付", "B", filename),               # 交付/B 文件夹（C→B 交付）
        os.path.join(project_root, "交付", "C", filename),               # 交付/C 文件夹
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _load_team_aliases() -> dict[str, str]:
    """加载球队别名映射表。

    从 D/team_aliases.json 读取，建立「中文名/英文名 → team_id」的映射。
    例如："法国" → "team_FRA", "France" → "team_FRA", "法兰西" → "team_FRA"

    如果文件不存在则返回空字典（降级处理）。
    """
    import json
    alias_file = _find_file("team_aliases.json", "TEAM_ALIASES_PATH")
    if not alias_file:
        logger.warning("未找到 team_aliases.json，球队别名功能暂不可用")
        return {}

    try:
        with open(alias_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        aliases = data.get("aliases", {})
        logger.info(f"已加载 {len(aliases)} 条球队别名 ({alias_file})")
        return aliases
    except Exception as e:
        logger.warning(f"加载 team_aliases.json 失败: {e}")
        return {}


# 模块级缓存
_team_aliases: Optional[dict[str, str]] = None


def get_team_aliases() -> dict[str, str]:
    """获取球队别名映射（懒加载+缓存）。"""
    global _team_aliases
    if _team_aliases is None:
        _team_aliases = _load_team_aliases()
    return _team_aliases


def extract_filters(query: str) -> dict:
    """从自然语言问题中提取结构化过滤条件。

    这是 query rewrite 的第一步：在语义检索之前，先提取出可精确匹配的
    条件（年份、球队、阶段），用于 Chroma 的 metadata 过滤，缩小检索范围。

    球队匹配优先级：
    1. team_aliases.json 中的别名映射（覆盖 85 支球队的中英文名）
    2. 回退：team_ids 中的 team_ 前缀 ID

    参数:
        query: 用户原始问题，如 "2018年法国队在淘汰赛阶段的比赛结果"

    返回:
        {
            "tournament_year": 2018,
            "team": "法国",           # 用户问题中出现的球队名（用于展示）
            "team_id": "team_FRA",    # 标准化的 team_id（用于 Chroma 过滤）
            "stage": "决赛",
            "rewritten_query": "比赛结果",  # 去掉已提取条件的纯文本
        }
    """
    filters = {}
    aliases = get_team_aliases()

    # --- 年份提取 ---
    year_match = re.search(r"(19\d{2}|20\d{2})\s*年", query)
    if year_match:
        filters["tournament_year"] = int(year_match.group(1))

    # --- 球队名称提取（使用 team_aliases.json 中的别名） ---
    if aliases:
        # 按别名长度从长到短排序，优先匹配长名称（如"沙特阿拉伯"优先于"沙特"）
        sorted_aliases = sorted(aliases.keys(), key=len, reverse=True)
        for alias in sorted_aliases:
            if alias in query:
                team_id = aliases[alias]
                filters["team"] = alias
                filters["team_id"] = team_id
                logger.info(f"球队匹配: '{alias}' -> {team_id}")
                break

    # --- 阶段提取（使用 stage_mapping.json，支持中英文输入） ---
    sm = get_stage_mapping()
    d2e = sm.get("display_to_enum", {}) if sm else {}

    if d2e:
        # 按 key 长度降序排列，优先匹配长关键词（如"三四名决赛"优先于"决赛"）
        sorted_keys = sorted(d2e.keys(), key=len, reverse=True)
        for keyword in sorted_keys:
            if keyword in query.lower():
                stage_enum = d2e[keyword]
                filters["stage"] = stage_enum         # 英文 enum（用于 Chroma 过滤）
                filters["stage_name"] = sm.get("enum_to_display", {}).get(stage_enum, keyword)
                logger.info(f"阶段匹配: '{keyword}' -> {stage_enum}")
                break
    else:
        # 降级：硬编码中文阶段（stage_mapping.json 不可用时）
        exact_stages = {
            "小组赛": "group", "1/8决赛": "round_of_16", "1/4决赛": "quarter_final",
            "八强": "quarter_final", "半决赛": "semi_final", "四强": "semi_final",
            "三四名决赛": "third_place", "三四名": "third_place", "季军赛": "third_place",
            "决赛": "final", "冠军": "final",
        }
        for keyword, stage_enum in exact_stages.items():
            if keyword in query:
                filters["stage"] = stage_enum
                break

    # 宽泛阶段：不适用于 Chroma 精确过滤
    broad_stages = {"淘汰赛", "16强", "8强", "4强", "quarter", "semi"}
    if "stage" not in filters:
        for keyword in broad_stages:
            if keyword in query.lower():
                filters["stage_hint"] = keyword
                break

    # --- 生成简化后的查询文本 ---
    rewritten = query
    for pattern in [r"(19\d{2}|20\d{2})\s*年", r"(小组赛|淘汰赛|1/8决赛|1/4决赛|半决赛|三四名|季军赛|决赛)"]:
        rewritten = re.sub(pattern, "", rewritten)
    rewritten = re.sub(r"\s+", " ", rewritten).strip()
    filters["rewritten_query"] = rewritten if rewritten else query

    logger.info(f"Query Rewrite: '{query[:60]}...' -> filters={ {k:v for k,v in filters.items() if k != 'rewritten_query'} }")
    return filters


def query_rewrite(query: str) -> list[str]:
    """对查询做多角度改写，提升召回率。

    生成 2-3 个语义相似但表述不同的查询，合并检索结果。
    这是提升 Recall 的常用技巧。

    当前实现：基于规则的模板改写
    后续可升级：用 LLM 做 query expansion
    """
    variations = [query]  # 原始查询

    # 模板改写
    templates = [
        lambda q: q.replace("谁赢了", "获胜方"),
        lambda q: q.replace("比分", "比分为"),
        lambda q: q.replace("输给", "被击败"),
        lambda q: re.sub(r"(.*)对(.*)的战绩", r"\1与\2 历史交锋", q),
    ]
    for tmpl in templates:
        rewritten = tmpl(query)
        if rewritten != query and rewritten not in variations:
            variations.append(rewritten)

    if len(variations) > 1:
        logger.info(f"Query expansion: {len(variations)} 个变体")

    return variations

# ===================================================================
#              状态枚举 & 结构化返回
# ===================================================================


class RetrievalStatus:
    """检索服务状态码（对应 B 同学整改清单 5.7 和 D→E 契约）。

    使用方式：
        status = RetrievalStatus.OK        # 查询成功且有结果
        status = RetrievalStatus.EMPTY     # 查询成功但无满足阈值的证据
        status = RetrievalStatus.DEGRADED  # reranker 等增强模块不可用，已降级
        status = RetrievalStatus.ERROR     # 完全不可用
    """
    OK = "ok"
    EMPTY = "empty"
    DEGRADED = "degraded"
    ERROR = "error"


class RetrievalResponse:
    """结构化检索响应（对齐 02-D-to-E 契约 v2.0）。

    替代直接返回 list[dict]，让 E 能拿到完整的执行状态。
    """

    def __init__(
        self,
        query: str,
        candidates: list[dict],
        status: str = RetrievalStatus.OK,
        rewritten_query: Optional[str] = None,
        filters: Optional[dict] = None,
        config: Optional[dict] = None,
        warnings: Optional[list[str]] = None,
        timing: Optional[dict] = None,
    ):
        self.query = query
        self.status = status
        self.candidates = candidates
        self.rewritten_query = rewritten_query
        self.filters = filters
        self.config = config or {}
        self.warnings = warnings or []
        self.timing = timing or {}

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "status": self.status,
            "rewritten_query": self.rewritten_query,
            "filters": self.filters,
            "config": self.config,
            "candidates": [
                {
                    "text": c.get("document", ""),
                    "vector_score": c.get("distance"),
                    "rerank_score": c.get("rerank_score"),
                    "retrieval_rank": c.get("retrieval_rank", i + 1),
                    "rerank_rank": c.get("rerank_rank"),
                    "metadata": c.get("metadata", {}),
                }
                for i, c in enumerate(self.candidates)
            ],
            "execution": {
                "rewrite_applied": bool(self.rewritten_query),
                "reranker_applied": any(c.get("rerank_score") is not None for c in self.candidates),
                "warnings": self.warnings,
                "timing": self.timing,
            },
        }


# ===================================================================
#                   对外 API
# ===================================================================


def add_chunks(
    chunks: list[dict],
    collection: str = COLLECTION_FACTS,
) -> int:
    """批量写入 chunk 到指定 collection。

    参数:
        chunks: 字典列表，每个字典格式：
            {
                "id": "match_2018_final",
                "document": "2018年世界杯决赛，法国4:2克罗地亚...",
                "metadata": {
                    "match_id": "match_2018_final",
                    "tournament_year": 2018,
                    "stage": "决赛",
                    "team_ids": ["FRA", "CRO"],
                    "document_name": "世界杯事实库.json",
                    "source_url": "https://...",
                    "source_page": 1,
                    "chunk_index": 0,
                    "language": "zh",
                    "data_version": "v1.0",
                },
            }
        collection: 目标 collection（COLLECTION_FACTS 或 COLLECTION_REPORTS）

    返回:
        成功写入的 chunk 数量
    """
    if not chunks:
        raise ValueError("chunks 不能为空")
    if collection not in (COLLECTION_FACTS, COLLECTION_REPORTS):
        raise ValueError(f"未知的 collection: {collection}")

    # 拆成 Chroma API 需要的三个并列列表
    # 同时清理 metadata 中的 None 值（Chroma 不接受 None）
    ids = [c["id"] for c in chunks]
    documents = [c["document"] for c in chunks]
    metadatas = [
        {k: v for k, v in c["metadata"].items() if v is not None}
        for c in chunks
    ]

    col = get_facts_collection() if collection == COLLECTION_FACTS else get_reports_collection()

    # 使用 upsert（幂等写入），重复 id 自动覆盖而非插入
    col.upsert(ids=ids, documents=documents, metadatas=metadatas)
    logger.info(f"[{collection}] upsert {len(ids)} 个 chunk，当前总计 {col.count()} 条")
    return len(ids)


def _load_stage_mapping() -> dict:
    """加载 D/stage_mapping.json，提供 display→enum 和 enum→display 双向映射。"""
    import json
    path = _find_file("stage_mapping.json")
    if not path:
        logger.warning("未找到 stage_mapping.json，阶段过滤功能降级")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载 stage_mapping.json 失败: {e}")
        return {}


_stage_mapping: Optional[dict] = None


def get_stage_mapping() -> dict:
    """获取阶段映射表（懒加载+缓存）。"""
    global _stage_mapping
    if _stage_mapping is None:
        _stage_mapping = _load_stage_mapping()
    return _stage_mapping


def _display_to_enum(stage_name: str) -> str:
    """将阶段的中文名（或英文别名）转为标准英文 enum。

    例: "决赛"→"final", "semi-finals"→"semi_final", "quarterfinal"→"quarter_final"
    """
    sm = get_stage_mapping()
    d2e = sm.get("display_to_enum", {})
    # 1. 精确匹配
    if stage_name in d2e:
        return d2e[stage_name]
    # 2. 小写匹配
    lower = stage_name.lower().strip()
    for key, val in d2e.items():
        if key.lower().strip() == lower:
            return val
    # 3. 如果已经是有效 enum，直接返回
    valid = sm.get("valid_enums", [])
    if stage_name in valid:
        return stage_name
    # 4. 降级：返回原值
    return stage_name


def _build_where_filter(filters: dict) -> Optional[dict]:
    """将我们自己的 filter dict 转为 Chroma 的 where 格式。

    v2.1 数据使用英文 stage enum（如 "final"、"semi_final"），
    此函数会将用户输入的中文阶段名转换为英文 enum 后再过滤。
    """
    where_parts = []
    if "tournament_year" in filters:
        where_parts.append({"tournament_year": filters["tournament_year"]})

    if "stage" in filters:
        stage_enum = _display_to_enum(filters["stage"])
        where_parts.append({"stage": stage_enum})
    elif "stage_enum" in filters:
        # 直接传入英文 enum（跳过转换）
        where_parts.append({"stage": filters["stage_enum"]})

    # 优先用 team_id（标准 ID），其次用 team 名称
    if "team_id" in filters:
        where_parts.append({"team_ids": {"$contains": filters["team_id"]}})
    elif "team" in filters:
        where_parts.append({"team_ids": {"$contains": filters["team"]}})

    if not where_parts:
        return None
    if len(where_parts) == 1:
        return where_parts[0]
    return {"$and": where_parts}


def query_top_k(
    query_text: str,
    k: int = 5,
    collection: str = COLLECTION_FACTS,
    filters: Optional[dict] = None,
    use_query_rewrite: bool = True,
) -> list[dict]:
    """语义检索：输入自然语言问题，返回 Top-K 个 chunk。

    参数:
        query_text: 用户问题
        k: 返回数量
        collection: 查询哪个 collection
        filters: 结构化过滤条件（由 extract_filters() 生成）
        use_query_rewrite: 是否启用 query rewrite 提升召回

    返回:
        [
            {
                "id": "match_2018_final",
                "document": "...",
                "metadata": {...},
                "similarity": 0.95,
                "collection": "world_cup_match_facts",
            },
            ...
        ]
    """
    if not query_text or not query_text.strip():
        raise ValueError("query_text 不能为空")

    col = get_facts_collection() if collection == COLLECTION_FACTS else get_reports_collection()
    where = _build_where_filter(filters) if filters else None

    # --- Step 1: query expansion（可选）---
    queries = query_rewrite(query_text) if use_query_rewrite else [query_text]

    # --- Step 2: 执行检索 ---
    # 根据 embedding 模式选择查询方式
    ef = get_embedding_function()
    all_items = {}  # 用 id 去重合并

    for q in queries:
        if ef is not None and EMBEDDING_MODE == "bge":
            # BGE 模式：手动编码查询向量
            query_embedding = ef.encode_query(q)
            result = col.query(
                query_embeddings=[query_embedding],
                n_results=k * 2,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        else:
            # Chroma 内置模式：直接传文本，让 Chroma 自己编码
            result = col.query(
                query_texts=[q],
                n_results=k * 2,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

        if result["ids"] and result["ids"][0]:
            for i, chunk_id in enumerate(result["ids"][0]):
                if chunk_id not in all_items:
                    dist = result["distances"][0][i] if result.get("distances") else None
                    all_items[chunk_id] = {
                        "id": chunk_id,
                        "document": result["documents"][0][i] if result.get("documents") else "",
                        "metadata": result["metadatas"][0][i] if result.get("metadatas") else {},
                        "distance": round(dist, 4) if dist is not None else None,
                        "similarity": round(1 - dist, 4) if dist is not None else None,
                        "collection": collection,
                    }

    items = list(all_items.values())
    # 按相似度降序
    items.sort(key=lambda x: x["similarity"] if x["similarity"] is not None else 0, reverse=True)

    logger.info(f"查询「{query_text[:50]}...」→ 召回 {len(items)} 条")
    return items[:k]


def query_with_rerank(
    query_text: str,
    k: int = 5,
    collection: str = COLLECTION_FACTS,
    filters: Optional[dict] = None,
    recall_k: int = 20,
) -> list[dict]:
    """完整检索管线：粗筛（Embedding+Chroma）→ 精排（Reranker）。

    流程：
    1. Chroma 粗筛召回 Top-recall_k 条
    2. Reranker 精排取 Top-k 条
    3. 返回最终结果

    这比单纯 query_top_k 更准确，但多一次模型推理，延迟稍高。
    """
    # Step 1: 粗筛
    candidates = query_top_k(
        query_text=query_text,
        k=recall_k,
        collection=collection,
        filters=filters,
        use_query_rewrite=True,
    )

    if len(candidates) <= k:
        return candidates

    # Step 2: Reranker 精排（如果可用）
    docs = [c["document"] for c in candidates]
    reranker = get_reranker()
    ranked = reranker.rerank(query_text, docs, top_k=k)

    if not ranked:
        # Reranker 不可用，直接返回粗筛结果
        logger.info("Reranker 不可用，使用 Chroma 原始排序")
        return candidates[:k]

    # Step 3: 重组结果
    results = []
    for idx, score in ranked:
        item = candidates[idx].copy()
        item["rerank_score"] = round(float(score), 4)
        results.append(item)

    logger.info(f"Rerank: {len(candidates)} -> {len(results)} 条, Top-1: {results[0]['rerank_score'] if results else 'N/A'}")
    return results


def list_documents(collection: str = COLLECTION_FACTS) -> list[dict]:
    """列出指定 collection 中已存储的文档（按 match_id 去重）。"""
    col = get_facts_collection() if collection == COLLECTION_FACTS else get_reports_collection()

    try:
        all_data = col.get(include=["metadatas"])
    except Exception:
        logger.warning(f"[{collection}] 为空或获取失败")
        return []

    if not all_data["metadatas"]:
        return []

    doc_map: dict[str, dict] = {}
    for meta in all_data["metadatas"]:
        match_id = meta.get("match_id", "unknown")
        if match_id not in doc_map:
            doc_map[match_id] = {
                "match_id": match_id,
                "tournament_year": meta.get("tournament_year", ""),
                "stage": meta.get("stage", ""),
                "teams": meta.get("team_ids", []),
                "chunk_count": 0,
            }
        doc_map[match_id]["chunk_count"] += 1

    return sorted(doc_map.values(), key=lambda x: x["tournament_year"], reverse=True)


def delete_document(match_id: str, collection: str = COLLECTION_FACTS) -> int:
    """删除指定比赛的所有 chunk。"""
    if not match_id or not match_id.strip():
        raise ValueError("match_id 不能为空")

    col = get_facts_collection() if collection == COLLECTION_FACTS else get_reports_collection()

    try:
        existing = col.get(where={"match_id": match_id})
    except Exception:
        return 0

    if not existing["ids"]:
        logger.info(f"match_id={match_id} 不存在")
        return 0

    col.delete(ids=existing["ids"])
    logger.info(f"已删除 match_id={match_id}，共 {len(existing['ids'])} 个 chunk")
    return len(existing["ids"])


def get_collection_stats() -> dict:
    """获取两个 collection 的整体统计。"""
    facts = get_facts_collection()
    reports = get_reports_collection()

    facts_docs = list_documents(COLLECTION_FACTS)
    reports_docs = list_documents(COLLECTION_REPORTS)

    return {
        "world_cup_match_facts": {
            "total_chunks": facts.count(),
            "unique_matches": len(facts_docs),
            "years": sorted({d["tournament_year"] for d in facts_docs if d["tournament_year"]}),
        },
        "world_cup_reports": {
            "total_chunks": reports.count(),
            "unique_matches": len(reports_docs),
            "years": sorted({d["tournament_year"] for d in reports_docs if d["tournament_year"]}),
        },
    }


def reset_all():
    """清空两个 collection（仅开发用）。"""
    client = _get_client()
    for name in [COLLECTION_FACTS, COLLECTION_REPORTS]:
        try:
            client.delete_collection(name)
            logger.warning(f"已删除 collection: {name}")
        except Exception:
            pass
    logger.info("所有 collection 已重置")


def import_match_facts(json_path: str = "match_facts.json") -> int:
    """从 JSON 或 JSONL 文件批量导入比赛事实到 Chroma。

    支持格式（按优先级检测）：
    1. .jsonl → C 的 v2 格式（每行一个 JSON 对象，含 id/text/metadata）
    2. .json  → C 的 v1 格式（JSON 数组，含 text/metadata）

    v2 格式示例（对齐 01-C-to-D 契约 v2.0）：
        {"id": "match_fact_M-2018-64_v1", "text": "...", "metadata": {...}}

    v1 格式示例（向后兼容）：
        [{"text": "...", "metadata": {"match_id": "M-1930-01", ...}}]

    幂等性：使用 upsert，连续两次导入不会产生重复向量。

    参数:
        json_path: match_facts.json 或 match_facts.jsonl 文件路径

    返回:
        成功导入的 chunk 数量
    """
    import json

    # 自动检测 .jsonl 文件
    if not os.path.isfile(json_path) and os.path.isfile(json_path + "l"):
        json_path = json_path + "l"
        logger.info(f"自动检测到 JSONL 文件: {json_path}")

    if not os.path.isfile(json_path):
        # 使用通用查找（含 D/ 文件夹）
        found = _find_file(json_path)
        if found:
            json_path = found
        elif not os.path.isfile(json_path + "l"):
            pass  # 试试 .jsonl 后缀
        found_l = _find_file(json_path + "l") if not json_path.endswith(".jsonl") else None
        if found_l:
            json_path = found_l
            logger.info(f"在 D/ 中找到: {json_path}")

    if not os.path.isfile(json_path):
        raise FileNotFoundError(f"找不到文件: {json_path}（也搜索了 D/ 和 交付/ 目录）")

    logger.info(f"正在读取: {json_path}")

    # 检测格式
    is_jsonl = json_path.endswith(".jsonl")

    chunks = []
    if is_jsonl:
        # v2 格式：每行一个 JSON
        with open(json_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                meta = item["metadata"].copy()
                # v2 格式已含 id 字段，直接使用
                chunks.append({
                    "id": item["id"],
                    "document": item["text"],
                    "metadata": meta,
                })
    else:
        # v1 格式：JSON 数组
        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        for item in raw_data:
            meta = item["metadata"].copy()
            chunk_id = item.get("id", meta.get("match_id", f"unknown_{len(chunks)}"))
            chunks.append({
                "id": chunk_id,
                "document": item["text"],
                "metadata": meta,
            })

    # 统计
    years = sorted({c["metadata"].get("tournament_year") for c in chunks if c["metadata"].get("tournament_year")})
    stages = set(c["metadata"].get("stage") for c in chunks if c["metadata"].get("stage"))
    logger.info(f"准备导入 {len(chunks)} 条事实，覆盖年份 {years[0]}-{years[-1]}，阶段: {stages}")

    # 写入（upsert）
    count = add_chunks(chunks, COLLECTION_FACTS)
    logger.info(f"导入完成！成功写入 {count}/{len(chunks)} 条")
    return count


# ===================================================================
#              结果增强：球队名解析 + SQLite 详情 + 格式化
# ===================================================================

# --- 球队信息缓存 ---
_team_info: Optional[dict[str, dict]] = None


def _load_team_info() -> dict[str, dict]:
    """从 team_aliases.json 加载球队详情。"""
    global _team_info
    if _team_info is not None:
        return _team_info

    import json
    path = _find_file("team_aliases.json", "TEAM_ALIASES_PATH")
    if not path:
        logger.warning("未找到 team_aliases.json，球队信息不可用")
        _team_info = {}
        return _team_info

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _team_info = data.get("teams", {})
        logger.info(f"已加载 {len(_team_info)} 支球队信息")
    except Exception as e:
        logger.warning(f"加载球队信息失败: {e}")
        _team_info = {}
    return _team_info


def resolve_team_name(team_id: str) -> str:
    """team_id → 中文名。如 team_FRA → 法国。"""
    info = _load_team_info()
    team = info.get(team_id, {})
    return team.get("canonical_name", team_id)


def resolve_team_names(team_ids: list[str]) -> list[str]:
    """批量 team_id → 中文名。"""
    return [resolve_team_name(tid) for tid in team_ids]


# --- SQLite match 数据库 ---
_match_db_path: Optional[str] = None


def _get_match_db_path() -> Optional[str]:
    """查找 worldcup.db 路径。"""
    global _match_db_path
    if _match_db_path is not None:
        return _match_db_path if os.path.isfile(_match_db_path) else None

    # 优先使用环境变量，其次搜索常见路径
    db_path = _find_file("worldcup_v2.db", "WORLD_CUP_DB_PATH")
    if db_path:
        _match_db_path = db_path
        return db_path
    # fallback: 旧版 worldcup.db
    db_path = _find_file("worldcup.db")
    if db_path:
        _match_db_path = db_path
        return db_path
    logger.debug("未找到 worldcup_v2.db 或 worldcup.db，SQLite 增强功能不可用")
    return None


def get_match_detail(match_id: str) -> Optional[dict]:
    """从 worldcup.db 查询单场比赛的完整详情（比分/日期/场馆/胜者）。"""
    import sqlite3
    db_path = _get_match_db_path()
    if not db_path:
        return None

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM matches WHERE match_id = ?", (match_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            result = dict(row)
            # 将 team_id 转成中文名
            for key in ["home_team_id", "away_team_id", "winner_team_id"]:
                if key in result and result[key]:
                    result[key.replace("_id", "")] = resolve_team_name(result[key])
            return result
    except Exception as e:
        logger.warning(f"查询 match 详情失败 ({match_id}): {e}")
    return None


def get_goal_details(match_id: str) -> list[dict]:
    """从 worldcup.db 的 goals 表查询一场比赛的全部进球记录。

    返回（按进球时间排序）:
        [
            {
                "player": "Kylian Mbappe",        # 球员全名
                "team_name": "France",             # 进球方
                "minute_label": "65'",             # 进球时间
                "match_period": "second half",     # 比赛阶段
                "penalty": 0,                      # 是否点球
                "own_goal": 0,                     # 是否乌龙
            },
            ...
        ]
    """
    import sqlite3
    db_path = _get_match_db_path()
    if not db_path:
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT given_name, family_name, team_name, minute_label,
                   match_period, penalty, own_goal
            FROM goals
            WHERE match_id = ?
            ORDER BY minute_regulation
        """, (match_id,))
        rows = cur.fetchall()
        conn.close()

        goals = []
        for row in rows:
            r = dict(row)
            # 组装球员全名（西方习惯：given_name + family_name）
            first = (r.get("given_name") or "").strip()
            last = (r.get("family_name") or "").strip()
            full = f"{first} {last}".strip()

            goals.append({
                "player": full,
                "team_name": r.get("team_name", ""),
                "minute_label": r.get("minute_label", ""),
                "match_period": r.get("match_period", ""),
                "penalty": r.get("penalty", 0),
                "own_goal": r.get("own_goal", 0),
            })

        return goals
    except Exception as e:
        logger.warning(f"查询进球详情失败 ({match_id}): {e}")
        return []


def enrich_result(item: dict) -> dict:
    """增强单条查询结果：添加球队中文名 + match 完整详情。"""
    enriched = dict(item)
    meta = item.get("metadata", {})

    # 1. 球队名解析
    team_ids = meta.get("team_ids", [])
    if team_ids:
        enriched["team_names"] = resolve_team_names(team_ids)

    # 2. 从 SQLite 获取 match 详情（比分、胜者等）
    match_id = meta.get("match_id")
    if match_id:
        detail = get_match_detail(match_id)
        if detail:
            enriched["match_detail"] = detail

    # 3. 从 SQLite 获取进球详情
    if match_id:
        goals = get_goal_details(match_id)
        if goals:
            enriched["goals"] = goals

    return enriched


def format_result(item: dict, verbose: bool = False) -> str:
    """将增强后的查询结果格式化为可读字符串（调试/前端展示用）。"""
    meta = item.get("metadata", {})
    detail = item.get("match_detail", {})
    team_names = item.get("team_names", [])
    sim = item.get("similarity")
    rerank = item.get("rerank_score")

    year = meta.get("tournament_year", "?")
    stage = meta.get("stage", "?")
    score = detail.get("score_display") or meta.get("score_display", "?")

    teams_str = " vs ".join(team_names) if team_names else "? vs ?"

    score_tag = f"rerank={rerank:.4f}" if rerank is not None else f"sim={sim:.4f}" if sim is not None else ""

    result_type = detail.get("result_type") or meta.get("result_type", "")
    winner = detail.get("winner") or ""
    if winner:
        result_type += f" (胜者: {winner})"

    base = f"[{year}] {stage} | {teams_str} | 比分 {score} | {score_tag}"
    if result_type:
        base += f" | {result_type}"

    if verbose:
        date = detail.get("match_date", "")
        venue = detail.get("venue", "")
        if date:
            base += f"\n  日期: {date}"
        if venue:
            base += f"\n  场馆: {venue}"

        # 进球详情
        goals = item.get("goals", [])
        if goals:
            goal_lines = []
            for g in goals[:8]:  # 最多显示 8 球
                tag = ""
                if g.get("penalty"):
                    tag = " (点球)"
                if g.get("own_goal"):
                    tag = " (乌龙)"
                goal_lines.append(f"    {g['minute_label']} {g['player']} [{g['team_name']}]{tag}")
            if len(goals) > 8:
                goal_lines.append(f"    ... 还有 {len(goals) - 8} 球")
            base += "\n  进球:\n" + "\n".join(goal_lines)

        doc = item.get("document", "")
        if doc:
            base += f"\n  摘要: {doc[:150]}"

    return base


# ===================================================================
#              Async 包装（避免阻塞 FastAPI 事件循环）
# ===================================================================

# 注意：这些 async 函数仅仅是 asyncio.to_thread 的便捷包装。
# B 也可以直接用 run_in_threadpool 调用同步函数。
# 模型只需加载一次（已在模块级别做单例缓存），不会每个请求重复加载。


async def query_top_k_async(*args, **kwargs) -> list[dict]:
    """`query_top_k` 的 async 包装。在线程池中执行同步调用。"""
    import asyncio
    return await asyncio.to_thread(query_top_k, *args, **kwargs)


async def query_with_rerank_async(*args, **kwargs) -> list[dict]:
    """`query_with_rerank` 的 async 包装。"""
    import asyncio
    return await asyncio.to_thread(query_with_rerank, *args, **kwargs)


async def add_chunks_async(*args, **kwargs) -> int:
    """`add_chunks` 的 async 包装。"""
    import asyncio
    return await asyncio.to_thread(add_chunks, *args, **kwargs)


async def import_match_facts_async(*args, **kwargs) -> int:
    """`import_match_facts` 的 async 包装。批量导入不应在用户请求中调用。"""
    import asyncio
    return await asyncio.to_thread(import_match_facts, *args, **kwargs)


# ===================================================================
#         结构化查询接口（对齐 02-D-to-E 契约 v2.0）
# ===================================================================


def query_structured(
    query_text: str,
    k: int = 5,
    collection: str = COLLECTION_FACTS,
    filters: Optional[dict] = None,
    use_query_rewrite: bool = True,
    use_rerank: bool = False,
    recall_k: int = 20,
) -> RetrievalResponse:
    """执行检索并返回 D→E 契约格式的结构化响应。

    这是给 E（RAG 生成）调用的主接口。返回 RetrievalResponse
    而非裸 list[dict]，包含完整执行状态。
    """
    import time

    warnings_list = []
    timing = {}
    rewritten = None

    # 1. 提取过滤条件
    if filters is None:
        filters = extract_filters(query_text)

    rewritten = filters.get("rewritten_query") if "rewritten_query" in filters else None

    # 2. 检索
    t0 = time.time()
    if use_rerank:
        candidates = query_with_rerank(
            query_text=query_text,
            k=k,
            collection=collection,
            filters=filters,
            recall_k=recall_k,
        )
        reranker_applied = any(c.get("rerank_score") is not None for c in candidates)
        if use_rerank and not reranker_applied:
            warnings_list.append("reranker unavailable, fallback to vector ranking")
    else:
        candidates = query_top_k(
            query_text=query_text,
            k=k,
            collection=collection,
            filters=filters,
            use_query_rewrite=use_query_rewrite,
        )
        reranker_applied = False

    timing["retrieval_ms"] = round((time.time() - t0) * 1000)

    # 3. 添加排序位置
    for i, c in enumerate(candidates):
        c["retrieval_rank"] = i + 1
        # rerank_rank 暂与 retrieval_rank 一致（reranker 不可用时）
        if c.get("rerank_score") is not None and "rerank_rank" not in c:
            c["rerank_rank"] = i + 1

    # 4. 判断状态
    col = get_facts_collection() if collection == COLLECTION_FACTS else get_reports_collection()
    col_count = col.count()

    if col_count == 0:
        status = RetrievalStatus.ERROR
        warnings_list.append(f"collection '{collection}' is empty, retrieval unavailable")
    elif not candidates:
        status = RetrievalStatus.EMPTY
    elif reranker_applied is False and use_rerank:
        status = RetrievalStatus.DEGRADED
    else:
        status = RetrievalStatus.OK

    return RetrievalResponse(
        query=query_text,
        status=status,
        candidates=candidates,
        rewritten_query=rewritten,
        filters={k: v for k, v in filters.items() if k not in ("rewritten_query", "stage_hint")},
        config={"top_k": k, "reranker_enabled": use_rerank, "use_rewrite": use_query_rewrite},
        warnings=warnings_list,
        timing=timing,
    )


# ===================================================================
#                      独立测试入口
# ===================================================================


if __name__ == "__main__":
    print("=" * 60)
    print("世界杯知识库 — Chroma Service 测试")
    print("=" * 60)

    # ---- 测试假数据（模拟 C 处理后的世界杯数据）----
    mock_facts = [
        {
            "id": "match_2018_final",
            "document": (
                "2018年俄罗斯世界杯决赛，法国队对阵克罗地亚队。"
                "90分钟内比分为4:2，法国队获胜。"
                "进球球员：格列兹曼、博格巴、姆巴佩（法国）；佩里西奇、曼朱基奇（克罗地亚）。"
                "比赛地点：莫斯科卢日尼基体育场。"
            ),
            "metadata": {
                "match_id": "match_2018_final",
                "tournament_year": 2018,
                "stage": "决赛",
                "team_ids": ["法国", "克罗地亚"],
                "home_team": "法国",
                "away_team": "克罗地亚",
                "score_display": "4:2",
                "result_type": "regulation",
                "winner": "法国",
                "document_name": "世界杯事实库.json",
                "source_url": "https://www.fifa.com/worldcup/2018/final",
                "source_page": 1,
                "chunk_index": 0,
                "language": "zh",
                "data_version": "v1.0",
            },
        },
        {
            "id": "match_2018_semi_fra_bel",
            "document": (
                "2018年俄罗斯世界杯半决赛，法国队对阵比利时队。"
                "90分钟内比分为1:0，法国队获胜，乌姆蒂蒂头球破门。"
                "比赛地点：圣彼得堡体育场。"
            ),
            "metadata": {
                "match_id": "match_2018_semi_fra_bel",
                "tournament_year": 2018,
                "stage": "半决赛",
                "team_ids": ["法国", "比利时"],
                "home_team": "法国",
                "away_team": "比利时",
                "score_display": "1:0",
                "result_type": "regulation",
                "winner": "法国",
                "document_name": "世界杯事实库.json",
                "source_url": "https://www.fifa.com/worldcup/2018/semi-final-1",
                "source_page": 1,
                "chunk_index": 0,
                "language": "zh",
                "data_version": "v1.0",
            },
        },
        {
            "id": "match_2018_quarter_fra_uru",
            "document": (
                "2018年俄罗斯世界杯1/4决赛，法国队对阵乌拉圭队。"
                "90分钟内比分为2:0，法国队获胜。"
                "进球球员：瓦拉内、格列兹曼（法国）。"
            ),
            "metadata": {
                "match_id": "match_2018_quarter_fra_uru",
                "tournament_year": 2018,
                "stage": "1/4决赛",
                "team_ids": ["法国", "乌拉圭"],
                "home_team": "法国",
                "away_team": "乌拉圭",
                "score_display": "2:0",
                "result_type": "regulation",
                "winner": "法国",
                "document_name": "世界杯事实库.json",
                "source_url": "https://www.fifa.com/worldcup/2018/quarter-final-1",
                "source_page": 1,
                "chunk_index": 0,
                "language": "zh",
                "data_version": "v1.0",
            },
        },
        {
            "id": "match_2022_final",
            "document": (
                "2022年卡塔尔世界杯决赛，阿根廷队对阵法国队。"
                "90分钟内比分为2:2，加时赛后3:3平局。"
                "点球大战阿根廷4:2法国。"
                "最终阿根廷获胜，梅西梅开二度，姆巴佩帽子戏法。"
                "比赛地点：卢塞尔体育场。"
            ),
            "metadata": {
                "match_id": "match_2022_final",
                "tournament_year": 2022,
                "stage": "决赛",
                "team_ids": ["阿根廷", "法国"],
                "home_team": "阿根廷",
                "away_team": "法国",
                "score_display": "3:3(点球4:2)",
                "result_type": "penalties",
                "winner": "阿根廷",
                "document_name": "世界杯事实库.json",
                "source_url": "https://www.fifa.com/worldcup/2022/final",
                "source_page": 1,
                "chunk_index": 0,
                "language": "zh",
                "data_version": "v1.0",
            },
        },
    ]

    mock_reports = [
        {
            "id": "report_2018_fra_journey",
            "document": (
                "法国队在2018年俄罗斯世界杯的夺冠之路："
                "小组赛阶段，法国队以2胜1平的不败战绩获得C组第一。"
                "1/8决赛4:3力克阿根廷，姆巴佩独中两元闪耀全场。"
                "1/4决赛2:0战胜乌拉圭，半决赛1:0击败比利时。"
                "决赛中法国队4:2战胜克罗地亚，时隔20年再次捧起大力神杯。"
                "主教练德尚成为历史上第三位以球员和教练身份都赢得世界杯的人。"
            ),
            "metadata": {
                "match_id": "report_2018_fra_summary",
                "tournament_year": 2018,
                "stage": "总结",
                "team_ids": ["法国"],
                "document_name": "世界杯比赛报告.md",
                "source_url": "https://www.fifa.com/worldcup/2018/report-france",
                "source_page": 1,
                "chunk_index": 0,
                "language": "zh",
                "data_version": "v1.0",
            },
        },
    ]

    # ---- 测试 1：写入比赛事实 ----
    print("\n[测试 1] add_chunks -> world_cup_match_facts")
    count = add_chunks(mock_facts, COLLECTION_FACTS)
    print(f"  -> 写入了 {count} 条事实")

    # ---- 测试 2：写入比赛报告 ----
    print("\n[测试 2] add_chunks -> world_cup_reports")
    count = add_chunks(mock_reports, COLLECTION_REPORTS)
    print(f"  -> 写入了 {count} 条报告")

    # ---- 测试 3：精确事实查询 ----
    print("\n[测试 3] query_top_k: 2018年决赛谁赢了")
    results = query_top_k("2018年世界杯决赛谁赢了", k=3, collection=COLLECTION_FACTS)
    for r in results:
        print(f"  [{r['similarity']:.3f}] {r['document'][:80]}...")

    # ---- 测试 4：带过滤条件的查询 ----
    print("\n[测试 4] extract_filters + query_top_k: 2018年法国队在淘汰赛的表现")
    filters = extract_filters("2018年法国队在淘汰赛的比赛结果")
    print(f"  提取的过滤条件: { {k:v for k,v in filters.items() if k != 'rewritten_query'} }")
    print(f"  改写后的查询: {filters['rewritten_query']}")
    results = query_top_k(filters["rewritten_query"], k=3, collection=COLLECTION_FACTS, filters=filters)
    for r in results:
        print(f"  [{r['similarity']:.3f}] {r['document'][:80]}...")

    # ---- 测试 5：语义总结查询（查报告） ----
    print("\n[测试 5] query_top_k: 法国队2018年夺冠历程（从 reports 查）")
    results = query_top_k("法国队2018年怎么夺冠的", k=2, collection=COLLECTION_REPORTS)
    for r in results:
        print(f"  [{r['similarity']:.3f}] {r['document'][:80]}...")

    # ---- 测试 6：reranker 精排 ----
    print("\n[测试 6] query_with_rerank: 2018年决赛")
    results = query_with_rerank("2018年世界杯决赛", k=3, collection=COLLECTION_FACTS)
    for r in results:
        rerank_val = r.get('rerank_score')
        if rerank_val is not None:
            print(f"  [rerank={rerank_val:.3f}] {r['document'][:80]}...")
        else:
            print(f"  [chroma={r['similarity']:.3f}] {r['document'][:80]}...")

    # ---- 测试 7：查看统计 ----
    print("\n[测试 7] 统计信息")
    stats = get_collection_stats()
    for col_name, info in stats.items():
        print(f"  {col_name}: {info}")

    # ---- 测试 8：查看文档列表 ----
    print("\n[测试 8] 文档列表")
    docs = list_documents(COLLECTION_FACTS)
    for d in docs:
        print(f"  [{d['tournament_year']}] {d['stage']}: {', '.join(d['teams'])} ({d['chunk_count']} chunks)")

    print("\n" + "=" * 60)
    print("测试完成！")

    # 如果要清空测试数据重新跑，取消下面的注释：
    # reset_all()
