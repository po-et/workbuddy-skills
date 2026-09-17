---
name: frontend-ui-zh
description: 前端 UI 工程、生产级组件、无障碍（WCAG 2.1 AA）、响应式、状态管理选型、去掉"AI 味"的界面。当用户说「做个像样的页面别一股 AI 味」「组件怎么拆」「状态放哪」「要过无障碍」「响应式怎么做」「加载态和空态怎么设计」时使用。要点：组件同目录（实现/测试/stories/hook/类型）；组合优于配置；容器与展示分离；状态选最简单的（本地 → 提升 → Context → URL → 服务端状态 → 全局 store），prop 穿透不超三层；避免 AI 默认审美的八种表现（紫色渐变、全圆角、通用 hero、假文案、大留白、卡片网格、重阴影）；间距用刻度、标题不跳级、语义色 token；键盘可达、ARIA 标签、焦点管理、有意义的空态与错误态；移动优先四断点；骨架屏与乐观更新。改编自 addyosmani/agent-skills 的 frontend-ui-engineering（MIT）。
author: Captain
version: 0.1.0
display_name: "前端 UI 工程（生产级·无障碍）"
display_name_en: "Frontend UI Engineering (zh)"
description_zh: "做出像设计感工程师做的界面：组件架构与组合、最简状态选型、避开八种 AI 默认审美、设计系统刻度、WCAG 2.1 AA 无障碍、移动优先响应式、骨架屏与乐观更新。"
description_en: "Build UI that looks intentionally designed, not generated: component architecture and composition, simplest-state selection, avoiding eight AI-default aesthetics, design-system scales, WCAG 2.1 AA accessibility, mobile-first responsiveness, skeletons and optimistic updates."
examples_zh:
  - "做一个任务列表页面，要生产质量、过无障碍"
  - "这个页面看起来很 AI，帮我按设计系统改"
  - "这些状态该放 Context 还是 URL"
examples_en:
  - "Build a production-quality, accessible task list page"
  - "This page looks AI-generated, rework it to the design system"
  - "Should this state live in context or the URL"
metadata:
  { "openclaw": { "requires": { "bins": [] }, "os": ["darwin", "linux", "windows"], "emoji": "🎨" } }
---

# 前端 UI 工程

目标：界面像顶级公司里有设计意识的工程师做的，而不是生成出来的——真正遵守设计系统、正经的无障碍、深思的交互、没有通用的"AI 审美"。

## 组件架构
**同目录**：`TaskList/` 下放实现、测试、stories（如用）、复杂状态的自定义 hook、组件专属类型。
**组合优于配置**：`<Card><CardHeader><CardTitle/></CardHeader><CardBody>…</CardBody></Card>` 优于塞满 `title / headerVariant / bodyPadding / content` 的一个大组件。
**组件只做一件事**；**数据获取与展示分离**：容器管 loading / error / empty 三态并渲染展示组件，展示组件只管渲染。

## 状态管理：选最简单能用的
本地 `useState`（组件内 UI 状态）→ 提升（2–3 个兄弟共享）→ Context（主题、鉴权、语言：读多写少）→ URL 参数（筛选、分页、可分享的 UI 状态）→ 服务端状态（React Query / SWR：远程数据与缓存）→ 全局 store（Zustand / Redux：全应用共享的复杂客户端状态）。**prop 穿透不超过三层**，穿过不用它的组件就上 Context 或重组树。

## 避开 AI 默认审美
| AI 默认 | 为什么是问题 | 生产做法 |
|---|---|---|
| 到处紫色/靛蓝 | 模型选"安全"色，所有应用长一样 | 用项目自己的调色板 |
| 过多渐变 | 视觉噪音，和多数设计系统冲突 | 平面或按系统的克制渐变 |
| 全部大圆角 | 无视真实设计里的圆角层级 | 设计系统的圆角刻度 |
| 通用 hero 区 | 模板布局，与内容和需求无关 | 内容优先的布局 |
| 假文案 | 占位文本藏住真实内容暴露的换行/溢出 | 真实感的占位内容 |
| 到处大留白 | 均匀大内边距摧毁层级、浪费空间 | 一致的间距刻度 |
| 卡片网格 | 无视信息优先级与扫读模式 | 目的驱动的布局 |
| 重阴影 | 与内容抢注意力、低端设备渲染慢 | 克制或不用，除非系统规定 |

**间距**用刻度（0.25rem 的倍数或项目的刻度），不发明 13px、2.3rem。**标题层级**：h1 每页一个 → h2 区块 → h3 子区块，不跳级、不用标题样式做非标题。**颜色**用语义 token（`text-primary` `bg-surface` `border-default`）而不是裸 hex；对比度正文 4.5:1、大字 3:1；信息不只靠颜色传达（加图标、文字或纹理）。

## 无障碍（WCAG 2.1 AA）
**键盘**：每个可交互元素可聚焦——用 `<button>` 而不是 `<div onClick>`；必须用 div 时加 role、tabIndex、Enter/Space 处理。**ARIA**：无可见文字的按钮加 `aria-label`；表单 label 关联 input，或无可见标签时 `aria-label`。**焦点管理**：内容变化时移动焦点（弹窗打开聚焦关闭按钮），弹窗内困住焦点。**有意义的空态与错误态**：不给白屏——图标 + 标题 + 一句说明 + 一个行动按钮，容器 `role=status`。

## 响应式
移动优先：单列 → sm 两列 → lg 三列。在 320 / 768 / 1024 / 1440 四个断点测。

## 加载与过渡
内容区用骨架屏而不是转圈（`aria-busy` + `aria-label`）；乐观更新提升感知速度：先改本地缓存、失败回滚到之前快照。

## 合理化借口对照

| 借口 | 现实 |
|---|---|
| "无障碍是锦上添花" | 很多辖区是法律要求，也是工程质量标准 |
| "响应式以后再做" | 事后补比一开始做难 3 倍 |
| "设计没定，先不做样式" | 用设计系统默认值；没样式的 UI 给评审者坏的第一印象 |
| "只是原型" | 原型会变生产；把地基打对 |
| "AI 味先这样吧" | 它释放的是低质量信号；从一开始用项目的设计系统 |

## 红灯
组件超过 200 行（拆）；行内样式或任意像素值；缺错误态、加载态、空态；没测过键盘导航；颜色是状态的唯一指示（红/绿无文字或图标）；通用 AI 外观（紫色渐变、大卡片、模板布局）。

## 验收
- [ ] 渲染无 console 错误　- [ ] 全部可交互元素键盘可达（Tab 一遍）　- [ ] 读屏能传达内容与结构　- [ ] 320/768/1024/1440 都正常
- [ ] 加载、错误、空态齐全　- [ ] 遵循项目设计系统（间距、颜色、排版）　- [ ] 开发工具或 axe 无无障碍警告

---
改编自 [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) 的 `frontend-ui-engineering`（MIT）。改动见 ATTRIBUTION.md。
