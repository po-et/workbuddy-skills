# 记忆系统：实现参考

以下为可直接改写进项目的最小实现骨架（Python），生产中把伪嵌入换成真实嵌入模型、把内存结构换成真实数据库。

## 向量库

```python
import numpy as np

def cosine_similarity(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return 0.0 if na == 0 or nb == 0 else float(np.dot(a, b) / (na * nb))

class VectorStore:
    def __init__(self, dimension=768):
        self.dimension, self.vectors, self.metadata, self.texts = dimension, [], [], []

    def add(self, text, metadata=None):
        self.vectors.append(self._embed(text)); self.metadata.append(metadata or {}); self.texts.append(text)
        return len(self.vectors) - 1

    def search(self, query, limit=5, filters=None):
        q = self._embed(query)
        scored = []
        for i, vec in enumerate(self.vectors):
            score = cosine_similarity(q, vec)
            if filters and not self._matches(self.metadata[i], filters):
                score = -1
            scored.append((i, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [{"index": i, "score": s, "text": self.texts[i], "metadata": self.metadata[i]}
                for i, s in scored[:limit] if s > 0]

    def _embed(self, text):  # 演示用的确定性伪嵌入；生产替换为真实模型
        np.random.seed(hash(text) % (2**32)); v = np.random.randn(self.dimension)
        return v / (np.linalg.norm(v) + 1e-8)

    def _matches(self, meta, filters):
        for k, v in filters.items():
            if k not in meta: return False
            if isinstance(v, list):
                if meta[k] not in v: return False
            elif meta[k] != v: return False
        return True
```

**带元数据索引的向量库**：在 `add` 时额外按 `entity` 和 `valid_from/valid_until` 建倒排索引（entity → [indices]、time_range → [indices]），`search_by_entity(query, entity)` 只对该实体的条目打分排序。

## 属性图与实体登记

```python
import uuid

class PropertyGraph:
    def __init__(self):
        self.nodes, self.edges, self.entity_registry = {}, [], {}   # registry: name -> node_id，跨交互保持身份
        self.indexes = {"node_label": {}, "edge_type": {}}

    def get_or_create_node(self, name, label, properties=None):
        if name in self.entity_registry:
            return self.entity_registry[name]
        node_id = self.create_node(label, {**(properties or {}), "name": name})
        self.entity_registry[name] = node_id
        return node_id

    def create_node(self, label, properties=None):
        node_id = str(uuid.uuid4())
        self.nodes[node_id] = {"label": label, "properties": properties or {}}
        self.indexes["node_label"].setdefault(label, []).append(node_id)
        return node_id

    def create_relationship(self, source_id, rel_type, target_id, properties=None):
        edge_id = str(uuid.uuid4())
        self.edges.append({"id": edge_id, "source": source_id, "target": target_id, "type": rel_type, "properties": properties or {}})
        self.indexes["edge_type"].setdefault(rel_type, []).append(edge_id)
        return edge_id
```

查询：按 `rel_type`、源/目标 `label` 与简单 where 条件过滤 `edges`，返回 (source, relationship, target) 三元组；生产中换成真正的图数据库。

## 时态知识图谱

```python
from datetime import datetime

class TemporalKnowledgeGraph(PropertyGraph):
    def create_temporal_relationship(self, source_id, rel_type, target_id, valid_from, valid_until=None, properties=None):
        edge_id = super().create_relationship(source_id, rel_type, target_id, properties)
        edge = next(e for e in self.edges if e["id"] == edge_id)
        edge["valid_from"] = valid_from.isoformat()
        edge["valid_until"] = valid_until.isoformat() if valid_until else None
        return edge_id

    def query_at_time(self, pattern, query_time):
        out = []
        for e in self.edges:
            vf = datetime.fromisoformat(e.get("valid_from", "1970-01-01")); vu = e.get("valid_until")
            if vf <= query_time and (vu is None or datetime.fromisoformat(vu) > query_time):
                if pattern.get("type") and e["type"] != pattern["type"]: continue
                src = self.nodes.get(e["source"], {})
                if pattern.get("source_label") and src.get("label") != pattern["source_label"]: continue
                out.append({"source": src, "relationship": e, "target": self.nodes.get(e["target"], {})})
        return out
```

## 记忆整理器

触发：节点 + 边总数超过阈值（如 1000）。步骤：1) 按 (source, type) 分组找重复事实；2) 每组保留置信度最高的一条，把其余的属性合并进去后移除；3) 更新有效期；4) 重建索引。原则：**失效但不丢弃**——把被取代的事实标 `valid_until`，而不是物理删除，以支持时间旅行查询。

## 记忆-上下文集成器

构建上下文时：从任务里抽实体（生产用 NER，原型可用 `[[实体名]]` 约定）→ 逐实体取回记忆 → 格式化为「## 相关记忆」列表（每条带来源与时间）→ 拼到当前上下文 → 超过预算就截断。记忆段放在注意力偏好位置。

## 框架快速上手

**Mem0：**
```python
from mem0 import Memory
m = Memory()
m.add("偏好带类型标注的 Python 3.12", user_id="dev-alice")
results = m.search("用户偏好什么语言？", user_id="dev-alice")
```

**Graphiti（Zep 开源时态图引擎，Neo4j 后端）：**
```python
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
graphiti = Graphiti(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)   # 从环境变量读取
await graphiti.add_episode(name="user_conversation_42", episode_body="Alice 提到她一月份搬到了柏林。",
                           source=EpisodeType.message, source_description="与 Alice 的对话")
results = await graphiti.search("Alice 住在哪？")   # 语义 + 关键词 + 图遍历
```

**Cognee（ECL 流水线：add → cognify → memify → search）：**
```python
import cognee
from cognee.modules.search.types import SearchType
await cognee.add("./docs/"); await cognee.cognify(); await cognee.memify()
results = await cognee.search(query_text="任意查询", query_type=SearchType.GRAPH_COMPLETION)
chunks = await cognee.search(query_text="任意查询", query_type=SearchType.CHUNKS)  # 需要原文块时
```
