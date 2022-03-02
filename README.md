# Bangumi Takeout

两个简单的 Python 脚本，用于从 Bangumi 中导出自己的标注记录，并转换为方便查看的 HTML。默认情况下按照标注顺序从旧到新排列。

[导出后的 HTML 文件示例](http://nekonull.me/bangumi-takeout-py/)

* `fetch.py`：使用 Bangumi API 导出自己的收藏记录，并保存到 `takeout.json`
* `generate.py`：读取 `takeout.json`，生成 HTML
> `takeout.json` 中含有完整的 `subject`(条目) 和 `episode`(分集) 详情信息，`generate.py` 中只使用了一部分，如有需要也可以自行转换到其他格式。
* `mapping.py`：数据字典

## 环境
需要 Python 3.6 或以上版本，并需要安装 `requests` 和 `tqdm` 两个依赖。

[PDM](https://pdm.fming.dev/) 用户可以使用 `pdm sync` 安装依赖。 

## 数据源
本脚本支持两种数据源：在线 [Bangumi API](https://bangumi.github.io/api/#/) 或 本地 [Bangumi Archive](https://github.com/bangumi/Archive)。

使用这两个数据源的差异如下：
- 本地源需要提前下载并解压到本地
- 在线源受到限流策略影响，导出速度会慢于本地源

用这两个数据源得到的结果大体上一致，但存在细微差异，具体如下：
- 完成度计算：在线源提供了精确的分母（主要分集数），但本地源没有，使用 `type` 为 `0` （本篇）的分集数量估算分母
- 分集类型：在线源中有 4 个分集类型（本篇、SP、OP、ED），本地源多出 2 个类型（预告/宣传/广告、其他）

如果账户中标注条目数较少（<=100），可以使用在线源，否则推荐使用本地源。

## 使用


1. 生成 Access Token：打开 [Bangumi API OAuth](https://api.bgm.tv/v0/oauth/)，选择「允许」，将网页中的全部内容复制下来，并将其中「Access Token」填入 `fetch.py` 第 9 行
2. （如果使用本地源）下载数据：从 [Archive Release](https://github.com/bangumi/Archive/releases/tag/archive) 下载最新的 `dump.zip`，将其中 `episodes.jsonlines` 和 `subject.jsonlines` 两个文件解压到脚本所在目录下
3. 运行 `fetch.py`，正常执行完成后应得到 `takeout.json`
4. 运行 `generate.py`，正常执行完成后应得到 `takeout.html`，用浏览器打开即可

## 工作原理
先获取用户自身 uid/username，然后获取全部收藏，最后对每个条目逐个获取条目详情、条目内分集（如有）和个人标准进度。

## 已知限制
- （使用在线源）为了避免对 API Server 造成过大负载，目前在 `fetch.py` 中手动用 `LOAD_WAIT_MS` 变量，在每个请求前等待至少 200 ms。对于收藏量较多的账户，本脚本可能运行较长时间。（100 条目需要约 2min）


## 可能的下一步
> 欢迎 PR！
- [ ] 完全用前端实现（需要前端大触）
- [ ] 支持筛选和搜索
- [ ] 正确使用 Bangumi 的 OAuth 认证，而不是手动填 Access Token
- [x] 使用 [Bangumi/Archive](https://github.com/bangumi/Archive) 作为本地数据源
- [ ] 写个简单的 GUI 界面
- [ ] 点格子之外，支持日志和时间胶囊？（似乎没有 API）
- [ ] 整理输出层级，加 `--verbose`
- [ ] 裁剪用到的 CSS 和 Javascript 代码，构造一个完全 self-contained，无外部依赖的 HTML 文件
- [ ] 完成度异常（不存在总集数）时使用 `striped` 进度条样式？
- [ ] 未播出分集使用 `disbaled` 样式？

## Bug 回报

如有可能请尽量附上完整的 stack trace 和使用的 `takeout.json` 文件。如文件过大无法加入 issue 附件，可以先压缩，然后手动添加一个 `.txt` 后缀名。

## 版本历史

* v1.1.2 - 修复音乐分集标注错误问题（见 #2）
* v1.1.1 - 修复完成度总为 100% bug
* v1.1.0 - 支持本地源、新增全部折叠/收起按钮、支持自动跳过无数据的 tooltip 属性
* v1.0.1 - 修复分集详情页链接不工作、新增分集进度异常时自动跳过（见 #1）
* v1.0.0 - 初版本