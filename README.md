# Bangumi Takeout

两个简单的 Python 脚本，用于从 Bangumi 中导出自己的标注记录，并转换为方便查看的 HTML。

[示例](http://nekonull.me/bangumi-takeout-py/)

* `fetch.py`：使用 Bangumi API 导出自己的收藏记录，并保存到 `takeout.json`
* `generate.py`：读取 `takeout.json`，生成 HTML
> `takeout.json` 中含有完整的 `subject`(条目) 和 `episode`(分集) 详情信息，`generate.py` 中只使用了一部分，如有需要也可以自行转换到其他格式。
* `mapping.py`：数据字典

## 环境
需要 Python 3.6 或以上版本，并需要安装 `requests` 和 `tqdm` 两个依赖。

[PDM](https://pdm.fming.dev/) 用户可以使用 `pdm sync` 安装依赖。 

## 使用
0. 生成 Access Token：打开 [Bangumi API OAuth](https://api.bgm.tv/v0/oauth/)，选择「允许」，将网页中的全部内容复制下来，并将其中「Access Token」填入 `fetch.py` 第 9 行
1. 运行 `fetch.py`，正常执行完成后应得到 `takeout.json`
2. 运行 `generate.py`，正常执行完成后应得到 `takeout.html`，用浏览器打开即可

## 工作原理
先获取用户自身 uid/username，然后获取全部收藏，最后对每个条目逐个获取条目详情、条目内分集（如有）和个人标准进度。

## 已知限制
为了避免对 API Server 造成过大负载，目前在 `fetch.py` 中手动用 `LOAD_WAIT_MS` 变量，在每个请求前等待至少 200 ms。对于收藏量较多的账户，本脚本可能运行较长时间。（100 条目需要约 2min）

## 可能的下一步
- [ ] 完全用前端实现（需要前端大触）
- [ ] 支持筛选和搜索
- [ ] 正确使用 Bangumi 的 OAuth 认证，而不是手动填 Access Token
- [ ] 使用 [Bangumi/Archive](https://github.com/bangumi/Archive) 作为本地数据源
- [ ] 写个简单的 GUI 界面
- [ ] 点格子之外，支持日志和时间胶囊？（似乎没有 API）
- [ ] 整理输出层级，加 `--verbose`