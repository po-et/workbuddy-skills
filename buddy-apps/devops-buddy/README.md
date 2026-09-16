# 研发效能 Buddy（DevOps Buddy）— Buddy 应用配置包

> 状态：**阻塞于企业认证**。2026-09-16 实测，个人开发者点击「创建」弹窗原文：
> 「个人开发者无法创建Buddy应用，如需创建，请进行企业认证，成为企业开发者」。
> 本目录是把应用的全部配置内容提前做好，认证一通过就能按表单逐项粘贴提交。

Buddy 应用不是代码包，是一份网页表单配置（官方文档《Buddy应用》：应用身份 / 首页 / 市场 / 其他 / 预览调试 五个模块）。
本包按这五个模块组织：

| 文件 | 内容 |
|---|---|
| `app.md` | 按后台表单顺序排好的粘贴稿：名称、slogan、描述、4 个工作模式（各带 system prompt）、8 个场景胶囊、市场绑定、模型偏好 |
| `config.json` | 同一份内容的机器可读版（非官方格式），`tools/check_buddy_app.py` 据此校验 |
| `assets/icon-256.png` | 应用头像 256×256（源文件 `assets/src/avatar.svg`） |
| `assets/icons/mode-*.svg` | 4 个工作模式图标，16×16、1.2px 线宽、带断口，按官方 icon 规则画 |
| `assets/scene-*-{day,night}.png` | 3 个精选场景底图，1000×910，按官方分层规范（底图 670px + 两层灰蒙层 + 全局蒙层）生成；自绘抽象图形，无第三方素材 |
| `assets/build.sh` | 重新生成上述图片（macOS qlmanage + ImageMagick 7） |

## 提交前置条件

1. 开放平台**企业认证**通过（个体工商户走腾讯云快速认证是否被接受，待确认）。
2. 要绑定的 9 个资产**先过审**（技能 4 / 专家 3 / 连接器 2，ID 见 `config.json`）。市场模块与模式绑定只能选已发布资产（据文档推测，待实测）。
3. 预览调试需要指定版本的 WorkBuddy 客户端（版本号以后台提示为准）。

## 校验

```bash
python3 tools/check_buddy_app.py buddy-apps/devops-buddy
```

## 设计依据

- 官方设计规范包 `buddy-app.zip`（首页：标题 + 工作模式 tab + 场景胶囊 + 输入框；专家页：精选场景卡片；icon 16×16/1.2px；底图 1000×910 分层）。
- 合作伙伴应用的公开结构（模块 + 专家 + 场景），见 `docs/buddy-app-plan.md`。
