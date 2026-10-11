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

`run` 使用仓库目录名作为默认 suite（当前为 `system-term`），保留 `HOME`，并清理 Agent Deck 会话及 API 相关环境变量后启动。

## 品牌、更新与边界

开发产物显示名称 `CFBundleName` 和 `CFBundleDisplayName` 为 `Teft`；主 bundle identifier 仍是 `com.googlecode.iterm2`，可执行文件仍为 `iTerm2`。因此它不是独立 bundle ID 的应用，也不能据此认定可使用 CU。显示名称变化不会改变 CU 授权状态。

Teft 开发版会阻断上游 Sparkle 更新，包括自动、手动和 delegate 更新路径。

目前尚未安装到 `/Applications`，也未进行签名公证发布或完整的视觉与交互验收。Agent Deck、World Store、PolarisAtlas 的深度集成仍是后续工作，尚未实现。
