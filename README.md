# RosieChinese — 网站文案校对版

网站设计稿的静态预览，加了一层「点击即改」的文案编辑器，给老师直接在页面上改文字用。

**在线：** https://freeyy.github.io/rosie-chinese/

## 老师怎么用

1. 打开网页，右下角有一个「文案修改」面板，把开关拨到「编辑中」。
2. 点页面上任何一段文字，直接改。按 **Enter** 保存，按 **Esc** 放弃这一处。
3. 改过的文字会有点状下划线；面板里列出每一处修改，可以单独「撤销」。
4. 换页请用屏幕底部的深色导航条（编辑模式下，页面里的按钮和链接是拿来改文字的，不会跳转）。
5. 改完点面板里的「复制修改记录」，把粘贴板里的内容发给我们即可。也可以点「下载」拿到一份 JSON 文件。

修改自动保存在这台设备的浏览器里，关掉网页再打开还在。换一台设备或浏览器则看不到，所以改完请及时复制发出。

预约、结账、学生后台、老师后台里的人名和数字是演示数据，不可编辑。图片和视频不在这里改，另有一张清单。

## 修改记录怎么对回源码

每处修改记录的是被改元素的原始 HTML（`before`）、改后的 HTML（`after`）、所在页面和模板节点编号 `tpl`（运行时给每个模板元素打的 `data-dc-tpl`）。同一段文字在多处出现的（比如首页滚动的学生评价和 Stories 页），只记一条，页面上会一起换掉。在 `src/RosieChinese_v2.dc.html` 里按 `before` 的文字搜索即可定位。

## 目录

| 路径 | 说明 |
| --- | --- |
| `build.py` | 用 `src/` 生成 `index.html`：内联运行时、React、字体声明和编辑器；给每个页面的 `<main>` 加 `data-screen`；去掉调色的开发工具；把模板里会让 React 报错的 `onmouseover` 字符串改成 CSS hover |
| `src/RosieChinese_v2.dc.html` | Claude Design 导出的设计文件，原样保留 |
| `src/editor.js` | 文案编辑器（面板、点击编辑、按原文重新套用改动、localStorage、导出） |
| `src/support.js` | Claude Design 运行时 |
| `src/react*.min.js` | React 18.3.1 UMD |
| `src/fonts.css` | 指向 `fonts/` 的 `@font-face` |
| `index.html` | 生成物，整站一个文件 |
| `assets/`、`fonts/` | 照片、字体 |
| `docs/editable-fields.md` | 可编辑文案清单：每一段可点击修改的文字，带编号 |
| `test/` | 见下 |

## 重新生成与测试

```sh
python3 build.py                 # 生成 index.html
cd test
python3 enumerate.py             # 枚举全部可编辑字段 → fields.json + docs/editable-fields.md
python3 e2e.py                   # 逐条点击、修改、验证，写 e2e-report.md
python3 visual.py                # 与 git HEAD 的 index.html 逐页截图比对，写 visual-report.md
```

测试用 Python 版 Playwright（`pip install playwright && playwright install chromium`）。

编辑器判定「一段可编辑文字」的规则在 `src/editor.js` 和 `test/fields_lib.py` 里各有一份实现：枚举脚本用自己的一份产出清单，端到端测试再拿这份清单去验证编辑器，两边不一致会直接以失败暴露出来。

设计稿更新后：把新的 `RosieChinese_v2.dc.html` 覆盖到 `src/`，重新执行上面四步。
