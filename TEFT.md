# Teft 开发说明

Teft 是基于官方 [iTerm2 源码](https://github.com/gnachman/iTerm2)的独立 fork，目前处于 macOS 开发版阶段。当前开发仓库位于 `system/main` 分支，并配置了 `upstream` remote；首次克隆后的准备步骤见 [README](README.md)。

## 首次准备与运行

在仓库根目录首次依次执行：

```sh
tools/teft.sh prepare
tools/teft.sh doctor
tools/teft.sh deps
tools/teft.sh build
tools/teft.sh run
```

`prepare` 初始化并更新子模块；`doctor` 检查构建依赖；`deps` 为当前 Xcode 重建原生依赖；`build` 构建 Development 版本并暂存应用；`run` 启动最新暂存版本。`status` 查看分支、HEAD、上游地址和子模块状态，`help` 查看命令说明。构建目录固定为 `build/teft`。

需要完整 Xcode 和 Homebrew，具体构建工具及原生依赖以 `doctor` 输出为准。本机已用 Xcode 26.2、Swift 6.2.3 在 arm64 上成功构建，期间包含部分 Swift 兼容修复；尚未验证从干净克隆完成整套构建。依赖或框架重编译会改变仓库内本地产物与构建 stamp；这些是本机生成状态，检查和暂存时不要把它们一并加入，也不要未经确认执行清理。

## 产物与运行隔离

构建日志写入 `tmp/teft-build.log`，依赖日志写入 `tmp/teft-deps.log`。每次构建会在 `build/teft/staged/teft-<timestamp>-<random>/Teft.app` 创建新的版本化产物，不覆盖旧版本。脚本执行 ad hoc deep codesign，并以 strict 模式校验。最新产物记录保存在 `tmp/teft-stage.json`。

`run` 使用仓库目录名作为默认 suite：当前本地目录为 `system-term`，按 README 克隆到默认目录 `teft` 时则使用 `teft`，不会强制改用另一套配置。启动时保留 `HOME`，清理 Agent Deck 会话及 API 相关环境变量，再通过 macOS Launch Services 打开暂存的应用包。切换到新的构建前应先正常退出已运行的 Teft，以免系统激活旧进程。

## 品牌、更新与边界

开发产物显示名称 `CFBundleName` 和 `CFBundleDisplayName` 为 `Teft`，主 bundle identifier 为 `com.teft.app`，主可执行文件为 `Teft`。两个自有 XPC 服务和导入辅助应用分别使用 `com.teft.app.sandboxed-worker`、`com.teft.app.pidinfo` 和 `com.teft.app.import-status`；客户端按主应用的服务配置连接。辅助组件的显示名使用 Teft，辅助执行文件、第三方框架、调试动态库和上游协议名称保留。

主包和各语言 `InfoPlist.strings` 的权限说明同步使用 Teft，保留原权限用途与键集合。可运行 `python3 tests/test_teft_stage_branding.py` 检查本地化格式与文字替换；这项检查不触发系统授权弹窗。

退出确认、恢复说明、退出原因、应用菜单、设置页、关于页产品标题及常见授权提示也使用 Teft。staging 按明确的表与键清单覆盖六种语言的显示值，并补入英文覆盖表，避免程序内的上游英文默认值漏出；本地化查询键、菜单标识和其他资源保留。上游赞助者、版权署名、第三方产品及协议名称不改写。需要正常退出旧版并启动新构建后，新的界面文案才会生效。

这些标识由 Teft staging 在版本化副本中设置，并在签名后核对；上游 Xcode 原生构建和测试身份保留。新标识不代表 Computer Use 已获得授权。开发版不自动迁移旧 iTerm 数据目录，也不自动接管官方 `iterm2` URL 默认处理器。开发配置域由运行时的目录名 suite 决定；正式发布所需的自有 Team、app group、keychain access group 和全面凭证隔离尚未完成。

Teft 开发版会阻断上游 Sparkle 更新，包括自动、手动和 delegate 更新路径。

开发版已在运行 macOS 26.5.2 的 MacBook Pro 上安装到 `/Applications/Teft.app` 并启动，文件完整性与签名校验、终端主进程及 shell 启动已验证。这次安装使用开发构建，尚未进行正式签名公证发布，也未完成原生权限弹窗、视觉与交互的完整验收。Agent Deck、World Store、PolarisAtlas 的深度集成仍是后续工作，尚未实现。
