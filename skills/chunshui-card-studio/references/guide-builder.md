# 分区引导页构建器

命令：`python scripts/build_guide.py 源稿/引导页配置.json --out 引导页`

JSON是制作输入，不能作为引导页交付。必须实际执行构建，默认同时生成：

- `引导页_直接粘贴.txt`：完整HTML/CSS及交互代码，没有Markdown代码围栏、JSON外壳或省略号；交给用户复制到引导页 HTML。
- `引导页_本地预览.html`：同一成品的独立预览；直接打开可填写、汇总与复制开局。
- `cardqa.plan.json`：生成可选的内部验收清单，不是用户引导页。TXT与预览HTML字节相同，均包含完整页面。

不覆盖现有同名文件、不上传或发布。`--compatibility`是明确的备用展示。改编`assets/guide-content.example.json`的真实内容，新增字段使用稳定唯一key。构建完成会自动运行交付检查；手工修改后再次执行 `python scripts/check_guide_delivery.py 引导页`。检查通过只证明交付内容完整一致；另按browser-qa.md运行随附行为测试或记录手动检查结果，平台保存另外验证。最后向用户链接前两份成品，配置留在源稿中；不让用户手动运行构建程序。

若平台验证后产生适配版本，应同步TXT、预览、重新验收，避免复制到旧版本。

## 配置

原有title/subtitle/world/play/characters/openings/fields仍可读取，但旧配置会缺合理分组。新卡不要沿用所有字段都是textarea的写法。

```json
{
  "title":"作品名",
  "subtitle":"一个有具体处境的短引子。",
  "theme":"rose-letter",
  "kicker":"作品题签",
  "eyebrow":"A NEW CHAPTER",
  "quote":"作为首屏旁注的作品主题句。",
  "entry_note":"玩家的身份、动机与入场处境。",
  "badges":["日常群像","自由设定","多种开局"],
  "background":"",
  "world":"背景介绍；段落之间用两个换行。",
  "play":"如何开始与推进故事。",
  "characters":[{"name":"林遥","role":"29岁 · 店主","appearance":"具体外貌","history":"有因果的经历","personality":"处事方式","relationship":"关系入口"}],
  "openings":[{"title":"初次相遇","text":"完整开局前提；只汇总选中的这一条。"}],
  "fields":[
    {"key":"name","label":"姓名或称呼","type":"text","group":"基础身份","placeholder":"如何称呼你"},
    {"key":"age","label":"年龄","type":"text","group":"基础身份","placeholder":"自定义年龄，关联经历需一致"},
    {"key":"identity","label":"身份与职业","type":"text","group":"基础身份"},
    {"key":"appearance","label":"外貌与衣着","type":"textarea","group":"外貌与性情"},
    {"key":"personality","label":"性格与习惯","type":"textarea","group":"外貌与性情"},
    {"key":"history","label":"背景与经历","type":"textarea","group":"经历与关系"},
    {"key":"relations","label":"既有关系","type":"textarea","group":"经历与关系"}
  ],
  "custom_people":false,
  "fixed_notes":["仅放这张卡确实固定的前提。"]
}
```

theme有rose-letter信笺与jade-scroll玉色卷首两个起点；按题材调整CSS/题签，主题选择不是全部设计。background接受https或PNG/JPEG/WebP data图片，不接受文件系统路径或可执行SVG。

字段可选：default为明确默认值、hint为简短提示、wide占整行、required为真正必填、options用于select（字符串或value/label对象）。默认值进入开局，placeholder不进入。外貌/性格、经历/关系分栏，不退回一个“完整人设”框。数字年龄无通用写死范围，实际时间线由作品规则核对。

custom_people:true启用补充人物，各有独立资料、经历、关系，可增删。删除只影响本次草稿，不是删世界书人物。fixed_notes在结果中明确标出，不把玩家愿望当既定事实。自定义场景可做额外字段配合“自定义开局”选项。

## 行为

- 四区连续阅读，导航按钮滚动到本页相应区域，支持方向键/Home/End；不会跳外部浏览器。所有字段保持可见。多个组件互不串资料；动态可暂停并响应减少动态偏好。
- 填资料、选开局后点击汇总，结果来自控件当前值，不来自placeholder，不漏换行或特殊字符。
- 生成后改表单，再复制会先更新；若先手改结果又改表单，明确提示需要重新生成/保留手改内容，避免静默覆盖；点击重新生成才替换。
- Clipboard API失败再尝试兼容复制命令，均失败选中全文并提示；只有实际成功才显示成功。没有输出时复制禁用。
- 脚本被移除时章节仍可读、生成复制禁用、显示运行提示。不伪装成功，不绕过过滤。

## 检查命令

`node scripts/test_guide.cjs --file 引导页/引导页_本地预览.html --out 测试/引导页 --playwright-dir 已安装的playwright目录 --browser 浏览器可执行文件`

能require('playwright')可省目录。使用现有依赖，不要求新装大套件。临时服务只监听127.0.0.1，结束即关闭。剪贴板用受控替身测试成功/失败，不改变系统剪贴板；平台剪贴板另行实测。

工具检查可观察交互，不判断美感；人工看生成的首屏、人设与结果截图。记录布局、文字层次、控件可读性、未验证环境。不能把源码含copy当作复制功能通过。
