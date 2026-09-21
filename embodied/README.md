# OmniJev Embodied Lab

这是主项目的具身工作台，深度集成 [FBddcz/embodied-jev](https://github.com/FBddcz/embodied-jev)，固定上游 commit `59a00c60e0f80fa32d14df1a365166267505980c`。源代码及许可证保留于此目录；原文见 [README.upstream.md](README.upstream.md)。上游实测成绩没有导入 OmniJev 的结果。

在父目录运行 `./setup_embodied.sh`，然后 `./run_embodied.sh`。本机已安装，直接运行后者即可。浏览器访问 `http://127.0.0.1:8766`。

前端源码位于 `frontend/`，已构建资源位于 `src/embodied_jev/web/`。修改前端后可用 Node 22.12+ 执行 `npm ci && npm run build`，或使用本项目的 `pnpm-lock.yaml` 执行 `pnpm install --frozen-lockfile && pnpm run build`。

完整说明见 [集成架构与复现协议](../docs/EMBODIED_INTEGRATION.md)。
