# GMI 8791 生图接入

Nano Banana 2.1 的三个生图入口（九宫格、批量主图、单独生图）调用本机 GMI 号池，真实模型为 `gemini-nano-banana-2.1`。其他模型与视频保留原有路由。

## 本机安装

该适配器依赖现有 `D:\monid-pool\server\gmi.py`、`gmi_http.py`、账号加密与数据库，不是独立号池。此电脑已安装。

1. 将 `gmi_image.py` 复制到号池的 `server/` 目录。
2. 应用 `gmi_http_timeout.patch` 到 `server/gmi_http.py`，增加可选 timeout 参数（默认仍为35秒）。生图提交等待180秒，查询等待60秒；超时不自动重新提交。
3. 在 `server/main.py` 导入 `gmi_image`，添加 `app.include_router(gmi_image.router)`。
4. 在已有 startup 函数中调用 `await gmi_image.recover_tasks()`。
5. 重启 8791 服务，然后打开更新后的网站，设置中填写 GMI 生图地址与原号池连接码。

默认地址 `http://127.0.0.1:8791`。网站必须在号池所在电脑的浏览器使用；线上网站访问本地服务时，浏览器可能要求允许访问本地网络。本机可直接使用 `http://127.0.0.1:8791/fengye`（此电脑已安装该页面）。其他设备不能通过自己的 127.0.0.1 访问这台电脑。

## 行为

- `GET /api/gmi-image-connection`：检查连接及带 Key 的账号数量。
- `POST /api/gmi-image`：JSON 文生图或 multipart 参考图生图，每个任务一张；多张由网页逐个提交。
- `GET /api/gmi-image?task_id=...`：获取任务状态和成品图地址。
- API 使用 `X-Pool-Token` 验证连接码；账号密码、真实 API Key 不返回网页。
- 使用 ready 状态且有 Key 的 GMI 账号，优先登记余额较高的空闲账号；跳过已登记为零的账号。未知余额允许提交，由 GMI 判断是否足额，登记余额仅作为选择参考。
- 任务与调用 Key 加密保存，轮询始终使用原账号；服务重启后继续查询已有上游编号，不自动重复提交不确定结果的生成请求。
- 内联图片缓存到号池 `data/gmi-image-media/`，网页使用本机图片地址；本次图片生成不改写已登记余额。
- GMI 余额检查原先要求的强制重新登录逻辑保持不变；生图使用 API Key。

## 验证

`D:\dola-pool\.venv\Scripts\python.exe local-pool/test_gmi_image.py`

`node local-pool/test_frontend.js`

已在此电脑真实验证 Nano Banana 2.1 文生图和带参考图的编辑生图，均完成并返回 PNG；并验证新接口鉴权、模型映射、任务恢复及异常不重复提交。
