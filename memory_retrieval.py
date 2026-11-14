
"""
Memory v2 相关性检索。

Phase 3 Day 4:
- 支持中英文关键词
- 使用中文双字词项匹配
- 根据记忆名称、内容、类型计算相关性
- 根据 importance 和更新时间排序
- 不跨 Agent 检索
"""

import re
import unicodedata

import memory_store


MAX_SCAN_ITEMS = 2000
PAGE_SIZE = 500


# 常见的非主题性词项，不参与相关性评分
STOP_TOKENS = {
    "你好",
    "我的",
    "我们",
    "你们",
    "什么",
    "怎么",
    "如何",
    "一下",
    "这个",
    "那个",
    "可以",
    "是否",
    "知道",
    "记得",
    "告诉",
    "继续",
    "刚才",
    "之前",
    "现在",
    "一个",
    "一些",
    "关于",
    "觉得",
    "请问",
    "以及",
    "还有",
    "了吗",
    "的是",
    "我想",
    "你能",
    "the",
    "and",
    "for",
    "are",
    "what",
    "how",
    "you",
    "your",
    "my",
    "with",
}


# 少量中英文名称对应关系
# 后续可以继续扩充，不是完整的语义词典
KEY_ALIASES = {
    "language": "语言 中文 英文 英语",
    "programming": "编程 代码 开发",
    "code": "代码 编程",
    "learning": "学习",
    "study": "学习",
    "project": "项目",
    "career": "职业 就业 实习",
    "internship": "实习",
    "goal": "目标 计划",
    "style": "风格",
    "preference": "偏好 喜好",
    "name": "名字 姓名",
    "assistant": "助手",
}


TYPE_LABELS = {
    "profile": "个人信息 身份",
    "preference": "偏好 喜好",
    "project": "项目 开发",
    "fact": "事实 信息",
    "goal": "目标 计划",
}


TOKEN_PATTERN = re.compile(
    r"c\+\+|c#|[a-z0-9]+|[\u4e00-\u9fff]+"
)


def tokenize(text):
    """
    将文本转换为关键词集合。

    英文：按单词拆分。
    中文：使用相邻双字作为轻量词项。

    例如：
        "学习 Python"
        -> {"学习", "python"}
    """

    if not isinstance(text, str):
        raise ValueError("检索文本必须是字符串")

    normalized = unicodedata.normalize(
        "NFKC",
        text,
    ).casefold()

    tokens = set()

    for part in TOKEN_PATTERN.findall(normalized):

        if re.fullmatch(r"[\u4e00-\u9fff]+", part):

            if len(part) < 2:
                continue

            for i in range(len(part) - 1):
                token = part[i:i + 2]

                if token not in STOP_TOKENS:
                    tokens.add(token)

        else:
            if (
                part not in STOP_TOKENS
                and len(part) >= 2
            ):
                tokens.add(part)

    return tokens


def _key_tokens(memory_key):
    """记忆名称的词项，包括少量英文别名。"""

    result = tokenize(
        memory_key.replace("_", " ")
    )

    parts = re.findall(
        r"[a-z0-9]+",
        memory_key.lower(),
    )

    for part in parts:
        alias = KEY_ALIASES.get(part)

        if alias:
            result.update(tokenize(alias))

    return result


def score_memory(memory, query_tokens):
    """计算单条记忆与问题的相关性。"""

    key_tokens = _key_tokens(
        memory["memory_key"]
    )

    content_tokens = tokenize(
        memory["content"]
    )

    type_label = TYPE_LABELS.get(
        memory["memory_type"],
        "",
    )

    type_tokens = tokenize(type_label)

    key_hits = query_tokens & key_tokens
    content_hits = query_tokens & content_tokens
    type_hits = query_tokens & type_tokens

    # 名称命中权重大于内容命中
    # 记忆类型只提供轻量辅助
    score = (
        len(key_hits) * 5.0
        + len(content_hits) * 2.0
        + len(type_hits) * 0.5
    )

    return score


def search_relevant_memories(
    agent_id,
    query,
    *,
    limit=5,
    db_path=None,
):
    """
    按当前问题检索指定 Agent 的相关记忆。

    没有命中时返回 []，不强制注入无关记忆。

    当前采用 Python 端评分：
    最多扫描指定 Agent 的 2000 条记忆。
    """

    if not isinstance(query, str):
        raise ValueError("query 必须是字符串")

    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 500
    ):
        raise ValueError(
            "limit 必须是 1～500 的整数"
        )

    query_tokens = tokenize(query)

    if not query_tokens:
        return []

    matched = []
    offset = 0

    while offset < MAX_SCAN_ITEMS:

        page_limit = min(
            PAGE_SIZE,
            MAX_SCAN_ITEMS - offset,
        )

        # memory_store 会按照 agent_id 过滤
        batch = memory_store.list_memories(
            agent_id,
            limit=page_limit,
            offset=offset,
            db_path=db_path,
        )

        if not batch:
            break

        for memory in batch:

            score = score_memory(
                memory,
                query_tokens,
            )

            if score <= 0:
                continue

            item = {
                **memory,
                "relevance_score": score,
            }

            matched.append(item)

        offset += len(batch)

        if len(batch) < page_limit:
            break

    # 采用稳定排序：
    # 第一优先级：相关性得分
    # 第二优先级：记忆重要程度
    # 第三优先级：更新时间
    matched.sort(
        key=lambda item: (
            item["updated_at"],
            item["created_at"],
            item["id"],
        ),
        reverse=True,
    )

    matched.sort(
        key=lambda item: item["importance"],
        reverse=True,
    )

    matched.sort(
        key=lambda item: item["relevance_score"],
        reverse=True,
    )

    return matched[:limit]
