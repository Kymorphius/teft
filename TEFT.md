# Teft 开发说明

Teft 是基于官方 iTerm2 源码的本地开发构建。仓库位于 `system/main` 分支，官方仓库配置为 `upstream` remote。

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

本机已用 Xcode 26.2、Swift 6.2.3 在 arm64 上成功构建，期间包含部分 Swift 兼容修复。依赖或框架重编译会改变仓库内本地产物与构建 stamp；这些是本机生成状态，检查和暂存时不要把它们一并加入，也不要未经确认执行清理。

## 产物与运行隔离

构建日志写入 `tmp/teft-build.log`，依赖日志写入 `tmp/teft-deps.log`。每次构建会在 `build/teft/staged/teft-<timestamp>-<random>/Teft.app` 创建新的版本化产物，不覆盖旧版本。脚本执行 ad hoc deep codesign，并以 strict 模式校验。最新产物记录保存在 `tmp/teft-stage.json`。

`run` 使用仓库目录名作为默认 suite（当前为 `system-term`），保留 `HOME`，并清理 Agent Deck 会话及 API 相关环境变量后，通过 macOS Launch Services 启动暂存的应用包。切换到新的构建前应先正常退出已运行的 Teft，以免系统激活旧进程。

## 品牌、更新与边界

开发产物显示名称 `CFBundleName` 和 `CFBundleDisplayName` 为 `Teft`，主 bundle identifier 为 `com.teft.app`，主可执行文件为 `Teft`。两个自有 XPC 服务和导入辅助应用分别使用 `com.teft.app.sandboxed-worker`、`com.teft.app.pidinfo` 和 `com.teft.app.import-status`；客户端按主应用的服务配置连接。辅助组件的显示名使用 Teft，辅助执行文件、第三方框架、调试动态库和上游协议名称保留。

主包和各语言 `InfoPlist.strings` 的权限说明同步使用 Teft，保留原权限用途与键集合。可运行 `python3 tests/test_teft_stage_branding.py` 检查本地化格式与文字替换；这项检查不触发系统授权弹窗。

这些标识由 Teft staging 在版本化副本中设置，并在签名后核对；上游 Xcode 原生构建和测试身份保留。新标识不代表 Computer Use 已获得授权。开发版不自动迁移旧 iTerm 数据目录，也不自动接管官方 `iterm2` URL 默认处理器。开发配置域继续使用 `system-term`；正式发布所需的自有 Team、app group、keychain access group 和全面凭证隔离尚未完成。

Teft 开发版会阻断上游 Sparkle 更新，包括自动、手动和 delegate 更新路径。

目前尚未安装到 `/Applications`，也未进行签名公证发布或完整的视觉与交互验收。Agent Deck、World Store、PolarisAtlas 的深度集成仍是后续工作，尚未实现。
