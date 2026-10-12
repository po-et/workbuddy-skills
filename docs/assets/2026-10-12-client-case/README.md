# 2026-10-12 WorkBuddy 接口差分实测成果图

三张图是依据本次真实任务 JSON 和维护者独立核对绘制的**流程 / 结果图**，不是客户端截图。案例输入为公开合成订单。客户端执行方式为显式读取本地仓库中的 api-diff 0.1.1；不代表市场自动发现、第三方使用或客户项目。

- `01-verifiable-workflow.svg`：读取技能 → 本地执行 → 回归被发现 → 修正复验 → 人工核查。
- `02-four-business-differences.svg`：金额、数量、布尔类型、空值/缺失四处实际差异。
- `03-repaired-and-cross-checked.svg`：修正后0差异、实际忽略路径、不同响应哈希、输入及脚本核对。
- `result-evidence.json`：过滤后的本次 regressed/repaired/verification 数据、完整文件哈希。
- `asset-manifest.json`：SVG尺寸、SHA256与对应数据源。
- `figures-preview.html`：浏览器预览页，可逐幅检查字形、布局和清晰度。

SVG 为1600×920；同名 JPEG 由真实浏览器渲染并完整保留图文，稿件引用三张 JPEG。浏览器导出尺寸1214×698，像素原样保存，未编辑为客户端 UI。导出 PNG 时应通过真实渲染保留所有文字，不裁掉“非客户端截图”和适用范围。若投稿渠道不支持 SVG，可将同幅成果图导出为 PNG；导出不把它变成客户端截图。截图捕捉失败的原生界面，没有重建或伪造。

相关稿件：[我用 WorkBuddy 给自己的接口差分技能做一次验收](../../articles/09-WorkBuddy实测-接口差分验收.md)。截至2026-10-12，稿件未向外部征文渠道投递，也未发送QQ/邮件。
