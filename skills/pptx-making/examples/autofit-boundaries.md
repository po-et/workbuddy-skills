# 自动缩小边界：100% 不代表字号缩小

`a:normAutofit` 表示文本框使用自动适应；只有它记录的字体比例低于 100%，才能提示字号被缩小。它本身不能证明文字现在发生了裁切或溢出。

## 判定示例

以下均放在幻灯片文本框的 `a:bodyPr` 内，其他内容保持相同：

| XML | 本检查器的字体缩放判断 |
|---|---|
| `<a:normAutofit fontScale="100000"/>` | 100%，不报 `auto_shrink` |
| `<a:normAutofit fontScale="100%"/>` | 100%，不报 `auto_shrink` |
| `<a:normAutofit/>` | 属性缺省为 100%，不报 `auto_shrink` |
| `<a:normAutofit lnSpcReduction="20000"/>` | 只设置了行距减少，不报字号缩小 |
| `<a:normAutofit fontScale="62500"/>` | 62.5%，报 `auto_shrink` |
| `<a:normAutofit fontScale="62.500%"/>` | 同样为 62.5%，报 `auto_shrink` |
| `<a:normAutofit fontScale="NaN"/>` | 无法解释，报 `unresolved_font_scale`，请人工复核 |

检查器保守支持整数 1000–100000，以及归一化后在 1%–100% 的百分比写法。它不是完整的 OOXML schema 验证器，不宣称涵盖所有版本的 Strict/Transitional 分支。数值超出该范围、格式不支持或不是有限数字时，输出未确定问题，退出码为 3；不会悄悄按 100% 处理。

## 复跑同一份材料的变体

使用仓库公开合成材料 [after.pptx](https://github.com/po-et/workbuddy-skills/blob/main/examples/pptx-fonts/inputs/after.pptx)。下面只在输出副本的 `ppt/slides/slide1.xml` 中第一个文本框上设置比例，不改原件。这个部件在此合成材料中是放映第一页；其他 PPT 的实际放映顺序可能不同。将命令中的 `after.pptx` 替换为该公开材料的本地路径：

```bash
python3 - after.pptx <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

source = Path(sys.argv[1])
a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
variants = {"font-100": "100000", "font-62_5": "62.500%", "font-unknown": "NaN"}
for label, scale in variants.items():
    target = source.with_name(source.stem + "-" + label + ".pptx")
    if target.exists():
        raise SystemExit("输出已存在，先另选输入名：" + str(target))
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "x") as output:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename == "ppt/slides/slide1.xml":
                slide = ET.fromstring(data)
                body = next(slide.iter(a + "bodyPr"), None)
                if body is None:
                    raise SystemExit("slide1.xml 中没有文本框，请使用上述公开合成材料")
                for child in list(body):
                    if child.tag in {a + "normAutofit", a + "noAutofit", a + "spAutoFit"}:
                        body.remove(child)
                ET.SubElement(body, a + "normAutofit", {"fontScale": scale})
                data = ET.tostring(slide, encoding="utf-8", xml_declaration=True)
            output.writestr(info, data)
    print(target)
PY

python3 {baseDir}/scripts/pptx_check.py after-font-100.pptx --json
python3 {baseDir}/scripts/pptx_check.py after-font-62_5.pptx --json
python3 {baseDir}/scripts/pptx_check.py after-font-unknown.pptx --json
```

使用上述公开合成材料时，预期结果依次是：退出 0；退出 3 且有一个 `auto_shrink`；退出 3 且有一个 `unresolved_font_scale`。其他材料可能另有字号、标题等问题，应单独查看对应 issue code，不能只看总退出码。这里验证的是 XML 判定和原件只读，不是视觉渲染或真实用户采用。

## 依据

- [Microsoft：NormalAutoFit.FontScale](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.normalautofit.fontscale?view=openxml-3.0.1)：`100000` 表示 100%，省略属性时默认 100%。
- [Microsoft：NormalAutoFit](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.normalautofit?view=openxml-3.0.1)：提供 `92.000%` 示例，分别解释字体比例与行距减少。
- [Open XML SDK schema 数据](https://github.com/dotnet/Open-XML-SDK/blob/main/data/schemas/schemas_openxmlformats_org_drawingml_2006_main.json)：`a:CT_TextNormalAutofit/a:normAutofit` 的初始整数验证范围为 1000–100000。
