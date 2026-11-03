# 春水世界书JSON参考与脚本契约

依据：作者2026-09-15原生导出 `format=worldbook/version=1`；2026-09-25本地缓存解析器验证过的扩展字段。这里没有平台认证、稳定API或全作品导入格式的保证。

顶层：`format`字符串、`version`数字、`exportedAt`ISO时间、`title`字符串、`categories`数组、`entries`数组。不要包进Markdown再保存JSON。

分组：`id`唯一字符串、`name`、`color`、`description`、`sort`数字。

条目关键字段：

| 字段 | 参考值/含义 |
|---|---|
| id / entryName / content | 稳定ID、可读中文名、模型可读正文 |
| keywords / secondaryKeywords | 字符串数组；普通关键词也必须放数组 |
| enabled | 布尔值 |
| categoryId | 指向已有分组 |
| position / insertionPositions | `system_prompt` / `["system_prompt"]`；新旧兼容字段 |
| triggerArea / triggerAreas | 单值legacy与多值数组；参考核心只查`user`，人物入口查`user,assistant` |
| priority / scanDepth | 数字；本地参考100或40、深度1或2，不保证排序方向及裁剪效果 |
| caseSensitive / matchWholeWords | 中文参考false / false |
| matchLogic / regexMatch | `or` / false；特殊原生逻辑先确认 |
| triggerProbability | 参考100，按百分数 |

新增数组字段在旧客户端可能被忽略。fallback `triggerArea=all` 不等于数组排除system在旧版本仍有效，必须实际检查。`cardkit build`仅生成上述已知参考结构，不负责整卡导入。

## 可维护母稿

```json
{
  "title": "雨巷来信",
  "namespace": "2d0cbf41-ed3b-43a3-b68d-9bd0b03b592e",
  "groups": [{"key":"people","name":"人物","color":"#859A85"}],
  "entries": [{
    "key":"lin-core","group":"people","name":"林知夏·核心档案",
    "keywords":["林知夏","林师傅"],
    "content":"林知夏，27岁，修书师。谨慎但愿意解释自己的判断。雨巷书店可遇见她。",
    "areas":["user","assistant"],"depth":2,"priority":40
  }]
}
```

每部作品独立namespace，条目key稳定，改中文名时不必改key。`constant:true` 是本脚本的母稿约定，会生成简单 `[\s\S]` 正则、只查最近玩家消息，**并非平台原生constant字段**。只适用于你已接受该机制的短核心条目；不要给人物细档全设constant。

`init` 生成可运行的双条目教学母稿（人物+地点），其内容必须替换成用户作品。`build`为组和条目生成UUIDv5，并同时输出阅读稿与触发目录。它会拒绝空正文、重复key、缺失组和空关键词，默认拒绝覆盖已存在的目标文件。

旧书修复优先最小编辑现有JSON；不要为使用本脚本而强制转母稿、丢失未知字段或重置ID。原生导出新增字段需保留，能重导导入后核对更好。

## 验证的实际范围

`validate` 检查UTF-8可读、重复JSON键、顶层类型、关键字段类型、唯一ID、分组引用、关键词、布尔项、扫描区域等。对疑似RE2不支持的环视/反引直接报错；它不包含真正RE2引擎，其他复杂正则标为需目标引擎验证。

`simulate` 仅实现：普通子串OR/AND、大小写选项、每条区域/深度参考、概率100、无次级逻辑、简单正则 `[\s\S]` 或 `(?s).+`。复杂正则、概率、次级关键词、整词匹配会列为unsupported，绝不悄悄当作已通过。

模拟只分析传入user/assistant消息，不读取真实聊天、system、记忆或平台日志；不执行优先级裁剪、递归或token预算。命中条数/字符数仅用于发现过宽或缺失触发。

一条触发通过不证明全部支持。交付本地测试结论时附上字段参考来源和未验证项；线上检查导入数、中文名称、保存成功、实际命中及聊天输出。
