# Just One API - 小红书（RedNote）接口文档（路径与入参）

数据来源：官方文档目录页「Xiaohongshu - Just One API」
- 链接：https://doc.justoneapi.com/folder-60218129

## 通用说明
- 接口域名环境：
  - 中国区（较快）：http://47.117.133.51:30015
  - 全球区（境外更稳）：https://api.justoneapi.com
- 认证与调用：
  - 所有接口需在 query 中携带 token=YOUR_TOKEN（必填）
  - HTTP 方法：GET（除非官方文档另有说明）

> 说明：以下接口名称与分组依据官方目录页面；具体路径与入参按现行接口版本整理，若官方后续有版本更新（v2/v3/v7 等），以最新文档为准。

---

## 1）用户笔记列表 API（User Note List v2）
- 路径：`/api/xiaohongshu/get-user-note-list/v2`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `userId`（string，必填）：小红书用户 ID
  - `lastCursor`（string，可选）：翻页游标（增量抓取）

---

## 2）笔记搜索 API（Note Search v3）
- 路径：`/api/xiaohongshu/search-note/v3`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `keyword`（string，必填）：搜索关键词
  - `page`（integer，必填）：页码（从 1 开始），示例：`1`
  - `sort`（string，必填）：排序（默认 `general`）
    - 可选枚举：`general`（综合，默认）、`popularity_descending`（最热）、`time_descending`（最新）
  - `noteType`（string，必填）：笔记类型（默认 `_0`）
    - 可选枚举：`_0`（综合）、`_1`（视频筛选）、`_2`（图文筛选）

---

## 3）笔记详情 API（Note Detail v7）
- 路径：`/api/xiaohongshu/get-note-detail/v7`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `noteId`（string，必填）：笔记 ID

---

## 4）笔记评论 API（Note Comment v2）
- 路径：`/api/xiaohongshu/get-note-comment/v2`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `noteId`（string，必填）：笔记 ID
  - `sort`（string，可选）：评论排序
    - 可选枚举：`normal`（默认）、`latest`（最新）
  - `lastCursor`（string，可选）：翻页游标

---

## 5）评论回复 API（Sub-comment / Comment Replies v2）
- 路径：`/api/xiaohongshu/get-note-sub-comment/v2`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `noteId`（string，必填）：笔记 ID
  - `commentId`（string，必填）：评论 ID（一级评论的主评论 ID）
  - `lastCursor`（string，可选）：翻页游标（第一页无需传入）

---

## 6）用户信息 API（User Info v3）
- 路径：`/api/xiaohongshu/get-user/v3`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `userId`（string，必填）：用户 ID
  - `acceptCache`（boolean，可选）：是否接受缓存（默认 false），示例：`false`

---

## 7）用户信息 API（User Info v4）
- 路径：`/api/xiaohongshu/get-user/v4`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `userId`（string，必填）：用户 ID
  - `acceptCache`（boolean，可选）：是否接受缓存（默认 false），示例：`false`

---

## 8）用户笔记列表 API（User Note List v4）
- 路径：`/api/xiaohongshu/get-user-note-list/v4`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `userId`（string，必填）：用户 ID
  - `lastCursor`（string，可选）：上一页最后一条笔记的 ID（用于翻页）

---

## 9）笔记详情 API（Note Detail v3）
- 路径：`/api/xiaohongshu/get-note-detail/v3`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `noteId`（string，必填）：笔记 ID

---

## 10）笔记详情 API（Note Detail v9）
- 路径：`/api/xiaohongshu/get-note-detail/v9`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `noteId`（string，必填）：笔记 ID
  - `xsecToken`（string，必填）：安全令牌（参数名：`xsec_token`）

---

## 11）笔记评论 API（Note Comment v4）
- 路径：`/api/xiaohongshu/get-note-comment/v4`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `noteId`（string，必填）：笔记 ID
- 特性说明：不支持分页，仅返回第一页评论数据。

---

## 12）笔记搜索 API（Note Search v2）
- 路径：`/api/xiaohongshu/search-note/v2`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `keyword`（string，必填）：搜索关键词
  - `page`（integer，必填）：页码（从 1 开始），示例：`1`
  - `sort`（string，必填）：排序（默认 `general`）
    - 可选枚举：
      - `general`（综合，默认）
      - `popularity_descending`（最热）
      - `time_descending`（最新）
      - `comment_descending`（最多评论）
      - `collect_descending`（最多收藏）
  - `noteType`（string，必填）：笔记类型（默认 `_0`）
    - 可选枚举：`_0`（综合）、`_1`（视频）、`_2`（图文）
  - `noteTime`（string，可选）：时间范围筛选
    - 可选枚举：`一天内`（within one day）、`一周内`（within a week）、`半年内`（within half a year）

---

## 13）用户搜索 API（User Search v2）
- 路径：`/api/xiaohongshu/search-user/v2`
- 方法：GET
- 入参（Query）：
  - `token`（string，必填）：鉴权 Token
  - `keyword`（string，必填）：搜索关键词
  - `page`（integer，必填）：页码（从 1 开始），示例：`1`

---

## 备注
- 以上路径与入参以 Just One API 官方文档为准；如接口版本更新（例如 v2/v3/v7），以实际文档最新版本为准。
- 排序与类型的枚举值以官方文档最终发布为准，可在后续补充更完整列表。

---

## 排错与使用指引（新增）

单组件构建时若出现“statusMissingFieldsError / Please fill all the required fields.”，通常是因为以下必填项未正确填写：

- Just One API Token（token）：任何接口都必须携带，未填写或仍为默认值 YOUR_TOKEN 会导致鉴权失败。
- 搜索词（keyword）：在“按关键词采集笔记”模式下必填。
- 笔记链接或ID（note_input）：在“按笔记采集评论”模式下必填。
- 用户 UID（xhs_user_id）：在“按用户信息采集笔记”模式下必填。

从本仓库最新组件版本起，UI 会根据“模式”动态显示/隐藏字段，并仅将当前模式相关的核心输入标记为必填；隐藏字段不参与必填校验。如果仍看到缺失字段提示：

1. 检查模式是否正确（例如选择了“按关键词采集笔记”却没有填写“搜索词”）。
2. 在 Token 栏位填入真实可用的 Token，避免默认值。
3. 若是从上游组件连接参数（Message/Handle）注入，请在单组件模式下改为直接手动输入字符串。
4. 查看输出 JSON 的“错误”字段，组件会以中文详细说明缺失项与调试信息（例如原始输入）。

示例（关键词模式最小可用参数）：

```
环境：中国区
token：<你的真实 TOKEN>
模式：按关键词采集笔记
搜索词：小猫
笔记类型：全部
排序类型：综合
开始页：1
结束页：1
时间范围：一天内
作者详细信息：关闭（可选）
笔记详情(正文)：开启（默认）
```

若请求失败，输出会包含“请求信息”（含 path/url/环境/打码后的 token/params）与“meta.请求耗时”，用于定位问题。详情调用与作者信息调用的策略与失败回退亦会记录在“meta.版本选择”。

## （新增）缺失接口的请求路径与输出示例补充

以下为与 apitest 目录对比后缺失的接口输出示例。本节为便于校对，将“请求路径”与“输出示例（节选）”补齐；完整 JSON 已保存到 apitest 目录对应文件中。

> 说明：为避免本文档过于臃肿，输出示例仅展示开头若干行；完整输出请参见 apitest 目录下的 .pretty.json 文件。

### A. 用户笔记列表 API（User Note List v2）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-user-note-list/v2?token=rrZQl9kQ&userId=636519f2000000001f019e57`
- 完整输出文件：`apitest/user_note_list_v2.pretty.json`
- 输出示例（节选）：

```json
{
    "code": 0,
    "data": {
        "tags": [],
        "has_more": true,
        "notes": [
            {
                "niced": false,
                "desc": "#银渐层[话题]# #我家宠物好可爱[话题]# #猫咪日常[话题]# #他好像知道自己很可爱[话题]# #可爱宝宝[话题]# #小猫小狗书[话题]# #小猫书[话题]# #宠物生活月刊[话题]#",
                "collected_count": 27,
                "advanced_widgets_groups": {
                    "groups": [
                        {
                            "mode": 1,
                            "fetch_types": [
                                "guos_test",
                                "note_next_step",
                                "second_jump_bar",
                                "note_collection",
                                "cooperate_binds",
                                "rec_next_infos"
                            ]
                        }
                    ]
                },
                "time_desc": "4天前",
                "display_title": "宝宝你这么可爱 你知不知道呀",
                "likes": 361,
                "user": {
                    "nickname": "million酱",
                    "images": "https://sns-avatar-qc.xhscdn.com/avatar/63e88c892a8d49af27389548.jpg?imageView2/2/w/80/format/jpg",
                    "red_official_verify_type": 0,
                    "userid": "636519f2000000001f019e57"
                }
            }
        ]
    }
}
```

---

### B. 笔记搜索 API（Note Search v2）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/search-note/v2?token=rrZQl9kQ&keyword=小猫&page=1&sort=general&noteType=_0`
- 完整输出文件：`apitest/search_note_v2.pretty.json`
- 输出示例（节选）：

```json
{
    "code": 0,
    "data": {
        "query_intent": {
            "goodsIntent": 3,
            "search_ask_intent": true,
            "low_supply_intent": false
        },
        "items": [
            {
                "model_type": "note",
                "note": {
                    "collected": false,
                    "user": {
                        "followed": false,
                        "red_id": "laifufua",
                        "nickname": "来福爱猫条",
                        "userid": "6006d7cd000000000101ed53"
                    },
                    "id": "68d9e0ed000000001302a684",
                    "liked_count": 12520
                }
            }
        ]
    }
}
```

---

### C. 笔记详情 API（Note Detail v3）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-note-detail/v3?token=rrZQl9kQ&noteId=67deef0a000000001e001660`
- 完整输出文件：`apitest/get_note_detail_v3.pretty.json`
- 输出示例：暂未提供成功示例（后续补齐）。

---

### D. 笔记详情 API（Note Detail v7）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-note-detail/v7?token=rrZQl9kQ&noteId=690ad34a0000000004001e98`
- 完整输出文件：`apitest/get_note_detail_v7.pretty.json`
- 输出示例（节选）：

```json
{
  "code": 0,
  "data": [
    {
      "user": {
        "userid": "62662b69000000002102742e",
        "nickname": "摸鱼Cici",
        "red_id": "2954786710",
        "image": "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo30o387tfqic605oj65dkoct1ef7gnmn8?imageView2/2/w/120/format/jpg"
      },
      "note_list": [
        {
          "id": "690ad34a0000000004001e98",
          "desc": "刚叫一个新员工过来问项目跟进情况，没说两句他Apple Watch就报警了[捂脸R]...",
          "images_list": [
            {
              "width": 1200,
              "height": 1600,
              "url": "https://sns-na-i8.xhscdn.com/1040g2sg31og8cqp15md05oj65dkoct1ehsr6oug?imageView2/2/w/1440/format/heif/q/46&redImage/frame/0&ap=1&sc=DETAIL..."
            }
          ],
          "liked_count": 2444,
          "comments_count": 1198,
          "ip_location": "广东",
          "time": 1762317130
        }
      ]
    }
  ]
}
```

---

### E. 笔记详情 API（Note Detail v9）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-note-detail/v9?token=rrZQl9kQ&noteId=67deef0a000000001e001660&xsec_token=笔记级分享链接中的xsec_token`
- 完整输出文件：`apitest/get_note_detail_v9.pretty.json`
- 输出示例：暂未提供成功示例（需笔记级分享链接的 xsec_token，后续补齐）。

---

## （续补）更多接口的最小输出示例

> 说明：以下为 apitest 目录中已抓取到的返回 JSON，基于“最小可读”原则选取关键字段，方便你快速对接与调试。

---

### F. 用户信息 API（User Info v4）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-user/v4?token=rrZQl9kQ&userId=636519f2000000001f019e57`
- 完整输出文件：`apitest/get-user_v4.pretty.json`
- 输出示例（节选）：

```json
{
  "code": 0,
  "data": {
    "userid": "636519f2000000001f019e57",
    "nickname": "million酱",
    "ip_location": "山东",
    "images": "https://sns-avatar-qc.xhscdn.com/avatar/63e88c892a8d49af27389548.jpg?imageView2/2/w/360/format/webp",
    "fans": 58963,
    "note_num_stat": {"posted": 410, "liked": 1176797, "collected": 114682},
    "share_link": "https://www.xiaohongshu.com/user/profile/636519f2000000001f019e57?xsec_token=YBYAWrqE3hCTi-M73SrjGo2N9RyurLsJy2I8HQERzmfWQ=&xsec_source=app_share"
  }
}
```

---

### G. 用户信息 API（User Info v3）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-user/v3?token=rrZQl9kQ&userId=636519f2000000001f019e57`
- 完整输出文件：`apitest/user_info_v3.pretty.json`
- 输出示例（节选）：

```json
{
  "code": 0,
  "data": {
    "fans": 58964,
    "ip_location": "山东",
    "images": "https://sns-avatar-qc.xhscdn.com/avatar/63e88c892a8d49af27389548.jpg?imageView2/2/w/360/format/webp",
    "red_id": "million_123",
    "note_num_stat": {"posted": 410, "liked": 1176802, "collected": 114682},
    "share_link": "https://www.xiaohongshu.com/user/profile/636519f2000000001f019e57?xsec_token=YBzuazDaZ_JC4yIUa8lrKVYdayK6fdUVsibsQIXiWo2aY=&xsec_source=app_share"
  }
}
```

---

### H. 用户笔记列表 API（User Note List v4）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-user-note-list/v4?token=rrZQl9kQ&userId=636519f2000000001f019e57`
- 完整输出文件：`apitest/user_note_list_v4.pretty.json`
- 输出示例（节选）：

```json
{
  "code": 0,
  "data": {
    "notes": [
      {
        "id": "6904d2400000000007037b4c",
        "type": "video",
        "create_time": 1761966044,
        "ip_location": "山东",
        "user": {
          "userid": "636519f2000000001f019e57",
          "nickname": "million酱",
          "images": "https://sns-avatar-qc.xhscdn.com/avatar/63e88c892a8d49af27389548.jpg?imageView2/2/w/80/format/jpg"
        },
        "images_list": [
          {
            "width": 1080,
            "height": 1440,
            "url": "https://sns-na-i11.xhscdn.com/1040g2sg31oacs69f4qe05or537p7r7inp3mcm3o?imageView2/2/w/576/format/heif/q/58|imageMogr2/strip&redImage/frame/0&ap=12&sc=USR_PRV&sign=041ed681a9bac8191f44c53a1fc5f30b&t=690b0041"
          }
        ]
      }
    ]
  }
}
```

---

### I. 笔记评论 API（Note Comment v2）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-note-comment/v2?token=rrZQl9kQ&noteId=67deef0a000000001e001660&sort=normal`
- 完整输出文件：`apitest/note_comment_v2.pretty.json`
- 输出示例（节选）：

```json
{
  "code": 0,
  "data": {
    "comment_count": 735,
    "comments": [
      {
        "id": "67e3b63e0000000012031b7e",
        "note_id": "67deef0a000000001e001660",
        "content": "虽然他有聪明毛，但看起来一点都不聪明，哈哈哈哈哈哈哈",
        "like_count": 162,
        "time": 1742976574,
        "user": {
          "userid": "5b88b234a76af2000100fb25",
          "nickname": "用户已注销",
          "images": "https://sns-avatar-qc.xhscdn.com/avatar/645b7e4b86578b8c6ab3b056.jpg?imageView2/2/w/120/format/jpg",
          "red_id": "294355065"
        }
      }
    ]
  }
}
```

---

### J. 笔记评论 API（Note Comment v4）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-note-comment/v4?token=rrZQl9kQ&noteId=67deef0a000000001e001660&sortType=hot`
- 完整输出文件：`apitest/note_comment_v4.pretty.json`
- 输出示例（节选）：

```json
{
  "code": 0,
  "data": {
    "comment_count": 735,
    "comments": [
      {
        "id": "67e3b63e0000000012031b7e",
        "note_id": "67deef0a000000001e001660",
        "content": "虽然他有聪明毛，但看起来一点都不聪明，哈哈哈哈哈哈哈",
        "time": 1742976574000,
        "like_count": 0,
        "user": {
          "user_id": "5b88b234a76af2000100fb25",
          "nickname": "用户已注销",
          "images": "https://sns-avatar-qc.xhscdn.com/avatar/645b7e4b86578b8c6ab3b056.jpg?imageView2/2/w/120/format/jpg",
          "red_id": "294355065"
        },
        "sub_comments": [
          {
            "id": "67e3e1ab000000001e03b500",
            "content": "但它的眼神充满了智慧[大笑R]",
            "time": 1742987692000,
            "user": {
              "user_id": "5fed7f31000000000100115e",
              "nickname": "冰火娃向前冲",
              "images": "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo31djt5nmh0k605nvdfsog84autg24tlg?imageView2/2/w/120/format/jpg",
              "red_id": "1102278698"
            }
          }
        ]
      }
    ]
  }
}
```

---

### K. 评论回复 API（Sub-comment v2）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/get-note-sub-comment/v2?token=rrZQl9kQ&commentId=67e3b63e0000000012031b7e&noteId=67deef0a000000001e001660`
- 完整输出文件：`apitest/note_sub_comment_v2.pretty.json`
- 输出示例（节选）：

```json
{
  "code": 0,
  "data": {
    "comments": [
      {
        "id": "67e3e1ab000000001e03b500",
        "note_id": "67deef0a000000001e001660",
        "content": "但它的眼神充满了智慧[大笑R]",
        "time": 1742987692,
        "user": {
          "userid": "5fed7f31000000000100115e",
          "nickname": "冰火娃向前冲",
          "images": "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo31djt5nmh0k605nvdfsog84autg24tlg?imageView2/2/w/120/format/jpg",
          "red_id": "1102278698"
        },
        "target_comment": {
          "id": "67e3b63e0000000012031b7e",
          "user": {
            "userid": "5b88b234a76af2000100fb25",
            "nickname": "用户已注销",
            "images": "https://sns-avatar-qc.xhscdn.com/avatar/645b7e4b86578b8c6ab3b056.jpg?imageView2/2/w/120/format/jpg",
            "red_id": "294355065"
          }
        }
      }
    ]
  }
}
```

---

### L. 用户搜索 API（User Search v2）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/search-user/v2?token=rrZQl9kQ&keyword=猫猫&page=1`
- 完整输出文件：`apitest/search_user_v2.pretty.json`
- 输出示例（节选）：

```json
{
  "code": 0,
  "data": {
    "users": [
      {
        "id": "5c03e9e3000000000701ecf5",
        "name": "猫猫",
        "image": "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo31ngkknsv5i004bup3hku7r7ldo2lhp0?imageView2/2/w/360/format/webp",
        "sub_title": "粉丝 5646",
        "desc": "小红书号：oovd29",
        "red_id": "oovd29"
      }
    ]
  }
}
```

---

### M. 笔记搜索 API（Note Search v3）
- 请求路径（带实参示例）：
  `GET http://47.117.133.51:30015/api/xiaohongshu/search-note/v3?token=rrZQl9kQ&keyword=小猫&page=1&sort=general&noteType=_0`
- 完整输出文件：`apitest/search_note.json`
- 输出示例（节选）：

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "note": {
          "id": "6789a1d1000000001c00dd10",
          "user": {
            "userid": "579980ce6a6a695e18b76f21",
            "nickname": "Milky酱",
            "images": "https://sns-avatar-qc.xhscdn.com/avatar/61e2e95263348c068bf2e558.jpg?imageView2/2/w/80/format/jpg"
          },
          "desc": "This is my cattax！Her name is Molly~Nice to meet u! @宠物薯 #吸猫",
          "liked_count": 19788
        }
      }
    ]
  }
}
```

---

### 附：可用的用户主页分享链接（含 xsec_token）
- 示例（来自用户信息接口返回）：
  `https://www.xiaohongshu.com/user/profile/636519f2000000001f019e57?xsec_token=YBYAWrqE3hCTi-M73SrjGo2N9RyurLsJy2I8HQERzmfWQ=&xsec_source=app_share`
- 作用与说明：
  - 该链接包含 xsec_token，可用于参考 xsec_token 的结构格式。
  - 但用于笔记详情 v9 时，需要“笔记级分享链接”中的 xsec_token（与用户主页的 xsec_token 不同）。因此不用 v9

---

