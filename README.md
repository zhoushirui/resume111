# 履历资料包助手 · Windows

采集百度百科正文与照片，将最终版提示词、人物信息和原始资料组合导出为 Word 资料包。手动把单个人的资料提供给 ChatGPT，不调用豆包或 GPT API，不需要 API Key。

## 下载和运行

1. 打开仓库 Actions → Build Windows EXE → 最近成功的运行。
2. 在 Artifacts 下载 ResumeMaterials-Windows-x64，解压后运行 dist/ResumeMaterials.exe。
3. 程序自动打开默认浏览器 http://127.0.0.1:18765。保留控制台窗口；关闭窗口或按 Ctrl+C 退出。
4. 输入“单位 姓名 职务”（支持从 Excel 粘贴），采集后在右侧选择人物和模式，下载资料包。
5. 将资料包交给 ChatGPT，按提示词生成单独的“单位名称_姓名_职位.docx”。

这是资料包工具，不会自动替你在 ChatGPT 内生成最终简历。推演模式的内容仍需人工核实，不应把未经证实的信息当作真实人事档案使用。

## 最终版布局

提示词要求最终文档标题居中，简介左侧为高 4 厘米、保持比例的照片，四周型文字环绕，仅右侧绕排，底部恢复全行；禁止表格、文本框、分栏。简介为一个连续段落。标题方正小标宋简体二号，正文仿宋_GB2312三号，分段标题黑体三号并缩进两字符，地区变化行楷体_GB2312三号，固定 28 磅行距。

提示词会保留浏览器内的编辑内容。需要恢复本版本默认提示词时使用页面的恢复默认按钮。Windows 中需自行安装具有合法使用权限的相应字体，否则 Word 可能替换字体。

## GitHub Actions 打包

本目录的内容应直接位于仓库根目录，包含隐藏的 .github 文件夹。推送 main 自动构建，也可在 Actions 页面手动 Run workflow。流程在 Windows x64 / Python 3.12 上安装依赖、测试、生成单文件 EXE，并启动 EXE 检查网页、静态资源和本地接口。无需配置仓库 Secrets。

未配置数字签名，Windows 可能提示未知发布者；请仅使用可信仓库构建的版本，不要关闭系统安全保护。此处没有附带任何 API 密钥、个人采集数据或字体文件。

## 本机开发（PowerShell）

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe launcher.py
```

本机打包：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm ResumeMaterials.spec
.\.venv\Scripts\python.exe tests/smoke_exe.py dist/ResumeMaterials.exe
```

必须在 Windows 上构建 Windows EXE，不能在 macOS 上用 PyInstaller 直接生成 Windows EXE。

## 注意

- 仅监听 127.0.0.1；浏览器和后端同源，不开放局域网服务。
- 页面依赖已随程序打包；采集百度百科仍需要联网。网络或目标站点限制可能导致抓取失败。
- 照片和正文保存在当前浏览器页面中，导出到你的电脑，不上传到本仓库。手动交给 ChatGPT 时请自行确认资料适合分享。
- 端口被占用时关闭旧程序，或执行 ResumeMaterials.exe --port 18766。
- 当前版本保留原有抓取逻辑；网页结构变化可能需要更新解析器。
