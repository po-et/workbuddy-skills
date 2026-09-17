# HTML 报告格式

架构评审渲染为一个自包含的 HTML 文件，放在系统临时目录，用绝对路径告知用户。Tailwind 和 Mermaid 都走 CDN。Mermaid 可靠地处理图状结构；手写 div 和内联 SVG 处理更有编辑感的视觉（质量图、剖面图）。两者混用：别什么都靠 Mermaid，会显得千篇一律。

## 脚手架

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>{{仓库名}} 架构评审</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
    </script>
    <style>
      /* Tailwind 不好覆盖的小自定义层：虚线接缝、手绘感箭头等 */
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: #dc2626; }
      .deep { background: linear-gradient(135deg, #0f172a, #1e293b); }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="candidates" class="space-y-10">...</section>
      <section id="top-recommendation">...</section>
    </main>
  </body>
</html>
```

## 页头

仓库名、日期、一个紧凑图例：实线框 = 模块，虚线 = 接缝，红箭头 = 泄漏，粗深色框 = 深模块。没有引言段落，直接进候选。

## 候选卡

图承担重量。文字稀疏、朴素，不带仪式感地使用「深模块设计」的术语。

每个候选一个 `<article>`：
- **标题**：短，点出加深的动作（如「折叠 Order 接单流水线」）。
- **徽章行**：推荐强度（`Strong` = 翠绿，`Worth exploring` = 琥珀，`Speculative` = 灰蓝），加一个依赖类别标签（`进程内`、`本地可替换`、`端口与适配器`、`mock`）。
- **文件**：等宽列表，`font-mono text-sm`。
- **前后对比图**：核心。两列并排。见下方图型。
- **问题**：一句话。哪里疼。
- **方案**：一句话。改什么。
- **收益**：要点，每条 ≤ 8 个字。如「测试只打一个接口」「定价逻辑不再泄漏」「删掉 4 个浅包装」。
- **ADR 提示**（如适用）：琥珀色框里一行。

没有解释段落。图需要一段话才能看懂，就重画图。

## 图型

按候选选合适的图型。混着用。别让每张图长得一样，多样性本身就是意图的一部分。

### Mermaid 图（依赖 / 调用流的主力）

要点是「X 调 Y 调 Z，看这一团乱」时用 Mermaid `flowchart` 或 `graph`。包在 Tailwind 卡片里，别像空降的。用 classDef 把泄漏边染红、深模块染深。时序图适合「之前：6 次往返；之后：1 次」。

```html
<div class="rounded-lg border border-slate-200 bg-white p-4">
  <pre class="mermaid">
    flowchart LR
      A[OrderHandler] --> B[OrderValidator]
      B --> C[OrderRepo]
      C -.泄漏.-> D[PricingClient]
      classDef leak stroke:#dc2626,stroke-width:2px;
      class C,D leak
  </pre>
</div>
```

### 手绘框线图（Mermaid 布局不听话时）

模块用带边框和标签的 `<div>`。箭头用内联 SVG 的 `<line>` 或 `<path>`，绝对定位覆盖在相对定位容器上。想让「之后」图呈现为一个粗边框深模块、内部灰化时用它，Mermaid 画不出那种分量。

### 剖面图（适合分层的浅）

水平色带（`h-12 border-l-4`）堆叠，展示一次调用穿过的层。之前：6 层薄薄的什么都不干；之后：1 条粗带，标着合并后的职责。

### 质量图（适合「接口和实现一样宽」）

每个模块两个矩形：一个是接口面积，一个是实现。之前：接口矩形几乎和实现一样高（浅）；之后：接口矩形矮、实现矩形高（深）。

### 调用图折叠

之前：函数调用树渲染为嵌套框。之后：同一棵树折叠成一个框，现已内部化的调用淡显在里面。

## 样式指南

- 偏编辑感，不是企业仪表盘。留白慷慨。标题可用衬线（`font-serif` 配 stone/slate 效果好）。
- 颜色克制：一种强调色（翠绿或靛蓝）加泄漏的红和警示的琥珀。
- 图高约 320px，前后并排不用滚动。
- 图内模块标签用 `text-xs uppercase tracking-wider`，读起来像示意图不像 UI。
- 唯一的脚本是 Tailwind CDN 和 Mermaid ESM 导入。报告其余部分静态：没有应用代码，没有 Mermaid 自带渲染之外的交互。

## 首推一节

一张更大的卡。候选名、一句为什么、锚点链接到它的卡。就这些。

## 语气

朴素、简洁，但架构的名词动词直接来自「深模块设计」词汇。简洁不是漂移的借口。

**精确使用：** 模块、接口、实现、深度、深、浅、接缝、适配器、杠杆、局部性。

**绝不替换成：** 组件、服务、单元（指模块时）· API、签名（指接口时）· 边界（指接缝时）· 层、包装（指模块时）。

**合适的措辞：**
- 「Order 接单模块是浅的：接口几乎等于实现。」
- 「定价跨接缝泄漏。」
- 「加深：一个接口，一处测试。」
- 「两个适配器让接缝成立：生产走 HTTP，测试走内存。」

**收益要点**用词汇表的词命名收益：*「局部性：bug 集中在一个模块」*、*「杠杆：一个接口，N 个调用点」*、*「接口收窄；实现吸收包装」*。不写*「更易维护」*或*「代码更干净」*，这些词不在词汇表里，配不上位置。

不含糊、不清嗓子、没有「值得一提的是……」。一句话能变要点就变要点。一个要点能删就删。词汇表没有的词，先找有的替，再考虑发明。
