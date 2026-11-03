# 春水与风月写卡工作室 · DeepSeek Harness Skills

作者：**wnyye** · 许可证：[MIT](LICENSE)

两份可独立安装的 DeepSeek Harness skill。用于把创意做成角色卡或大世界卡：世界书 JSON、人物与叙事规则、人物状态和记忆、聊天样式、可填写和复制开局的引导页，以及对应的填写说明。项目独立维护，不是 DeepSeek、春水或风月的官方插件。

| 平台 | 安装目录 | 版本 | 主要区别 |
|---|---|---|---|
| 春水 | [chunshui-card-studio](skills/chunshui-card-studio/SKILL.md) | 1.8.0 | 春水原生世界书参考格式；人设、输出格式和 CSS 分栏交付 |
| 风月 | [fengyue-card-studio](skills/fengyue-card-studio/SKILL.md) | 1.2.0 | 风月 world_book；输出结构写入主提示词，另交前置词、后置词及 CSS |

## 安装

1. 下载并解压仓库或发布包，进入里面的 **skills** 文件夹。
2. 复制需要的平台目录，也可以两个都复制。Windows 默认粘贴到 **%USERPROFILE%\.dsh\skills\**（可直接在资源管理器地址栏输入）；macOS/Linux 默认放到 **~/.dsh/skills/**。如果自定义了 DSH_HOME，使用该目录下的 skills。也可只装到某一个项目的 **.dsh/skills/**。
3. 检查结果应当是 **.dsh/skills/fengyue-card-studio/SKILL.md**，春水同理。不要把整个仓库再嵌套一层，也不要只拷贝 SKILL.md：脚本、素材、参考说明都在同级目录里。已有同名安装时先备份整份旧目录。
4. 新开 Harness 对话，点名使用相应 skill；如果没找到，先检查上一步的目录层级和当前 Harness 的技能发现配置。安装不需要开完全权限。详见 [DeepSeek Harness 官方技能目录说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/skill/skill-filesystem/README.md)。

## 第一次使用

例如，在 Harness 新对话中输入：

> 使用 fengyue-card-studio，帮我做一张雨夜书店题材的风月日常卡。玩家可以自定义姓名、年龄和职业。先只做世界书，在当前工作区单独建文件夹，给我可导入的 JSON、阅读版，以及“玩家不知道人名也能遇见店主”的触发测试。

换到春水时点名使用 chunshui-card-studio。两个 skill 可以共存；一次创作应指定目标平台。只想制作世界书、修复状态栏或修改引导页时，直接指定该部分即可。

## 功能与依赖

- **世界书**：人物有动机、经历与关系；关键人物有不依赖玩家事先知道姓名的相遇入口。成品按所选平台格式交付。
- **状态与记忆**：展示当前有效人物状态；字段原位更新，旧值不累加。长期／短期表每 6 个剧情轮归档，单条短期最多 150 字、单篇长期最多 400 字。已归档长期仍会增长。
- **引导页**：分栏编辑人设、选择开局、生成可编辑结果并复制。TXT 是可粘贴源码，HTML 用于本地预览。浏览器测试不等于平台嵌入测试。
- **工具**：制作、校验、消耗检查脚本使用 Python（建议 3.10+）。可选的引导页浏览器测试使用 Node.js、Playwright 与兼容浏览器；不随仓库分发这些依赖。Windows 复制助手使用 PowerShell。无需额外的私有验收插件。
- **使用边界**：脚本可在本地执行；真实模型生成、平台导入／保存和在线试玩需在各自环境核对。消耗统计是字符量与重复候选，不是价格预测。

## 不调用聊天模型的快速试用

先进入任一已解压的 skill 目录，以下两条命令适用于两个平台。示例输出目录应选择尚未使用的位置：

~~~sh
python scripts/build_guide.py assets/guide-content.example.json --out demo-guide
python scripts/check_guide_delivery.py demo-guide
~~~

打开 demo-guide 里的预览 HTML，填写资料、选择开局、生成并复制。正式创作时使用自己的配置，不要把示例角色当作成品交付。遇到兼容问题时，附上技能版本、目标平台、操作步骤和不含私人信息的最小示例即可。

## 授权及来源

随仓库分发的项目文件按 [MIT](LICENSE) 授权。单独转发其中一个 skill 时，也请保留该目录附带的 LICENSE。项目不包含平台客户端、用户作品集、创作者的原始参考图、模型权重或第三方插件。详见[来源说明](SOURCES.md)。
