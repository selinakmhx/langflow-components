# 小红书数据过滤器组件使用说明与过滤策略指南

这份文档介绍组件如何在三种模式下“保留相关、过滤明确噪声”，帮助你理解输出中保留的字段与被移除的字段。整体目标是：仅移除完全用不到的技术性噪声，所有有潜在相关性的内容尽量保留，尤其是多图片/多视频的 URL、用户与内容的核心要素。

重要提醒：需求文档里的“字段映射”并不精准，请以实际 JSON 为准；本组件策略基于 final 目录内的示例 JSON 综合制定。

## 组件功能与输入/输出

- 自动识别数据顶部“模式”（若缺失会尝试从“数据/result”等推断）
- 针对三种模式分别过滤：按关键词采集笔记、按笔记采集评论、按用户采集笔记
- 保留与业务相关的结构与字段：ID/标题/正文/用户/时间/计数/媒体 URL/元信息（meta）等
- 移除确定无用的技术指标（如 ssim/psnr/vmaf/rotate/quality_type 等），不影响后续业务处理

输入：Message（text 为 JSON 字符串或字典）
输出：Message（text 为过滤后的 JSON 字符串，保留顶部“模式”与 meta）

## 通用保留规则

- 保留结构与元信息：模式、环境、基础地址、数据/data、原始、meta、请求耗时、版本选择、统计、请求信息、页码、还有更多、下一页游标、code 等
- 保留内容与用户：note/notes/items/comments/user/用户信息 等结构节点及其关键字段
- 保留媒体与链接：url/urls/backup_urls/master_url/images/image/images_list/cover/thumbnail/first_frame、video_info/video_info_v2/media/stream/h264/h265 等
- 保留计数与时间：liked_count/likes/comments_count/collected_count/share_count/nice_count/view_count、create_time/time_desc/timestamp/update_time 等

## 明确过滤的技术噪声（跨模式统一移除）

- 视频编码评估/画质技术指标：ssim、psnr、vmaf
- 播放/流描述类技术细节：rotate、quality_type、stream_desc、default_stream
- 统计与体积类纯技术指标：weight、size、volume、audio_bitrate、audio_channels、video_bitrate

说明：上述键在业务侧（内容抽取、链接保留、用户/计数/时间分析）通常完全用不到，因此统一移除；其他可能相关的技术信息（如 width/height/format/fps/video_codec/avg_bitrate/video_duration）保留。

## 三种模式的具体保留要点

1) 按关键词采集笔记（模式包含“按关键词采集笔记”）
- 顶层：模式、meta、请求耗时、版本选择、统计、数据/data、原始、code、页码
- data 层：items、note、ads、user 等
- note 层：id/note_id/title/display_title/desc/type/timestamp/update_time/create_time/time_desc；
  liked_count/comments_count/collected_count/share_count/nice_count/view_count/is_goods_note；
  url（分享链接）；images_list（数组内所有 url 保留）；video_info/video_info_v2（保留 image、master_url、backup_urls 以及 width/height/format/fps/video_codec/avg_bitrate/video_duration 等，移除 ssim/psnr/vmaf/rotate/quality_type/stream_desc/weight/size/volume/audio_*、video_bitrate、default_stream）。
- user 层：userid/user_id/nickname/red_id/official_verified/red_official_verified 等。

2) 按笔记采集评论（模式包含“按笔记采集评论”）
- 顶层：模式、meta、请求耗时、版本选择、统计、result/data、请求信息
- 评论数据：comments 列表；每条保留 评论ID、用户（userid、nickname、images、red_id、official_verified）、小红书号、评论内容、点赞数、发布时间、发布地点、二级评论数、评论级别、作者ID、是否官方认证。

3) 按用户采集笔记（模式包含“按用户采集笔记”）
- 顶层：模式、环境、基础地址、数据/data、原始、meta、请求耗时、版本选择、统计、页码、还有更多、下一页游标、用户ID/用户信息、请求信息、code
- 用户信息：nickname/userid/fans/desc/red_id/images/share_link/interactions/type/name/count 等
- notes 列表：保留与“关键词采集笔记”模式相同的笔记与媒体字段（见上）。
 - 顶层聚合：组件会额外在顶层输出 notes_flat（聚合 数据[*].原始.data.notes），方便前端直接展示；不影响原始嵌套结构。

## 使用方法

1. 将上游 JSON（字符串或字典）作为组件输入（Message.text）
2. 组件自动识别模式并执行对应过滤；若模式缺失但存在“数据”，默认按“关键词采集笔记”处理
3. 输出为过滤后的 JSON 字符串，保留“模式”和“meta”，多图/多视频 URL 不会被删除
4. 组件会在顶层增加“过滤后统计”字段，包含 items/notes/comments 的条数，便于确认是否只是显示被截断而非数据缺失。
5. 也支持直接传入 .json 文件路径（绝对或相对路径），组件将自动读取并解析该文件；若传入的是路径但不可读或不是 JSON，将在状态中提示并返回空对象 {}。
5. 在“按用户采集笔记”模式下，顶层会额外提供 notes_flat 聚合列表，便于核对与展示；若看起来列表显示很短，请注意可能是前端预览截断。

## 注意与建议

- 字段映射请以实际 JSON 为准（final 目录示例），不要依赖不准确的需求文档映射表
- 任何可能相关的信息尽量保留，仅对明确技术噪声做统一移除
- 如果上游结构发生变化，可根据新样例调整“通用保留规则”和“噪声键”集合
- 输入不是合法 JSON 或无法确定模式时，组件会返回原始数据或空对象并在状态中提示

## 示例（片段）

示例：video_info_v2.stream[*] 中仅保留以下键：master_url、backup_urls、width、height、format、avg_bitrate、video_duration、fps、video_codec；
移除：ssim、psnr、vmaf、rotate、quality_type、stream_desc、weight、size、volume、audio_bitrate、audio_channels、video_bitrate、default_stream。

这样既确保所有可用媒体链接与必要媒体元信息被保留，同时有效降低无业务价值的数据噪声。