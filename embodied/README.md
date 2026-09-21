# OmniJev Embodied Lab

这是 OmniJev Vision Preview 的具身工作台。它提供本地 MuJoCo Panda 仿真、相机观测、有限候选动作、扰动、回放、模型对比和可复现 benchmark。源代码、资产许可和依赖说明保留于此目录。

在父目录运行 `./setup_embodied.sh`，然后 `./run_embodied.sh`。模型权重需要用户自行下载并由本地兼容后端加载；工作台只访问该后端的 HTTP API。浏览器访问 `http://127.0.0.1:8766`。

前端源码位于 `frontend/`，已构建资源位于 `src/embodied_jev/web/`。修改前端后可用 Node 22.12+ 执行 `npm ci && npm run build`，或使用本项目的 `pnpm-lock.yaml` 执行 `pnpm install --frozen-lockfile && pnpm run build`。

完整说明见 [集成架构与复现协议](../docs/EMBODIED_INTEGRATION.md)。
