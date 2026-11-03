# 引导页浏览器验收

从本 skill 目录运行以下命令。示例目录可自行替换；将中间文件和测试结果放在作品工作区，不要覆盖已安装的模板。

~~~sh
python scripts/build_guide.py assets/guide-content.example.json --out 示例引导页
python scripts/check_guide_delivery.py 示例引导页
~~~

正式作品须改用该作品的配置。成品是完整可粘贴 TXT 和本地预览 HTML。构建器同时生成 cardqa.plan.json 供兼容工具使用；公开版不依赖其他插件或作者电脑上的检查脚本。

## 交互和视觉检查

如有 Node.js、Playwright 和兼容浏览器，可运行随附的行为测试：

~~~sh
node scripts/test_guide.cjs --file 示例引导页/引导页_本地预览.html --out 验收结果
~~~

若测试找不到 Playwright，使用 --playwright-dir 指向已安装的 playwright 包，必要时用 --browser 指向浏览器可执行文件。详见[构建与交付](guide-builder.md)。剪贴板成功与拒绝分支使用受控替身；本地服务器只监听回环地址。

没有自动测试环境时，可用浏览器手动核对，并记录实际做过的项目：

- 桌面双栏、手机单列；检查 320、390、1280 像素下是否出现整页横向溢出。
- 逐项填写姓名、年龄、身份、外貌、性格、经历与关系，切换开局；结果只包含所选路线和真实填写内容。
- 生成后修改字段，不能复制旧值。手改汇总结果后不被静默覆盖。实测复制与失败后的手动选择；含尖括号的输入应按文字显示。
- 依次检查首屏、人物折叠、人设表单、汇总结果。核对减少动态、脚本不可用时的提示及按钮状态。多实例页面间的数据不能串用。
- 对最终交付版本截图并人工复核；无工具或未实测就写明。检查失败时修复成品再运行，不修改预期来掩盖问题。

以上检查只验证本地页面。平台保存后是否过滤脚本、是否允许复制，需要另在春水预览或试玩中验证。

设计与测试方法参考：[frontend-design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md)、[webapp-testing](https://github.com/anthropics/skills/blob/main/skills/webapp-testing/SKILL.md)。参考项目及依赖不随本包分发。
