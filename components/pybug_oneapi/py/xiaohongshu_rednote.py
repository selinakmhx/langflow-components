
from __future__ import annotations

"""
RedNote（小红书）组件

主要功能：
 - 按关键词采集笔记（仅用 search-note v2；不再调用笔记详情接口）
 - 按笔记采集评论（仅使用评论 v2；可选二级评论；不做分页；不做客户端点赞排序）
 - 按用户信息采集笔记（v4→v2；不再调用笔记详情接口）

输出：统一中文键 JSON，包含 meta（请求耗时、版本选择、统计），错误信息包含隐藏 Token 的请求路径。
"""

import json
import re
import time
import random
from typing import Any, Dict, List, Optional



import requests

from langflow.custom.custom_component.component import Component
from langflow.io import (
    BoolInput,
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    StrInput,
)
from langflow.schema.data import Data


class XiaohongshuRedNote(Component):
    display_name = "RedNote（小红书）"
    description = "面向 Just One API 的小红书组件：关键词笔记、用户笔记、笔记评论统一采集，输出中文键 JSON。已移除笔记详情相关开关，所有模式仅使用列表/评论接口（不调用 v7/v3 详情）。"
    documentation: str = "https://doc.justoneapi.com/"
    icon = "custom_components"
    name = "XiaohongshuRedNote"

    JOA_TOKEN: str = "YOUR_TOKEN"

    # 请求控制（不影响前台选项）：
    # - REQUEST_PRE_DELAY_MS：每次请求前的固定等待时间，避免触发服务端限流/瞬时拥堵
    # - REQUEST_TIMEOUT_SECONDS：单次请求的超时时间（默认 60 秒，略微上调以提升稳定性）
    # - REQUEST_RETRY_ATTEMPTS：遇到网络/服务端错误时的重试次数
    # - REQUEST_RETRY_BACKOFF_BASE_MS / REQUEST_RETRY_BACKOFF_JITTER_MS：指数退避基线与随机抖动，降低并发拥堵
    REQUEST_PRE_DELAY_MS: int = 800  # 每个请求前固定等待 0.8s
    REQUEST_TIMEOUT_SECONDS: int = 75  # 单次请求超时 75s（原 60s），减少“网络错误”概率
    REQUEST_RETRY_ATTEMPTS: int = 3  # 网络/5xx/429/无效JSON时最多重试 3 次
    REQUEST_RETRY_BACKOFF_BASE_MS: int = 600  # 退避基线 600ms（指数退避：600, 1200, 2400...）
    REQUEST_RETRY_BACKOFF_JITTER_MS: int = 400  # 退避抖动范围 0~400ms，避免踩同一时间窗

    ENV_BASE: Dict[str, str] = {
        "中国区": "http://47.117.133.51:30015",
        "全球区": "https://api.justoneapi.com",
    }

    PATHS: Dict[str, str] = {
        "user_info_v4": "/api/xiaohongshu/get-user/v4",
        "user_info_v3": "/api/xiaohongshu/get-user/v3",
        "user_note_list_v4": "/api/xiaohongshu/get-user-note-list/v4",
        "user_note_list_v2": "/api/xiaohongshu/get-user-note-list/v2",
        "search_note_v2": "/api/xiaohongshu/search-note/v2",
        "note_comment_v2": "/api/xiaohongshu/get-note-comment/v2",
        "note_sub_comment_v2": "/api/xiaohongshu/get-note-sub-comment/v2",
        }

    SEARCH_SORT_MAP: Dict[str, str] = {
        "综合": "general",
        "最热": "popularity_descending",
        "最新": "time_descending",
        "最多评论": "client_comments_desc",
        "最多收藏": "client_collected_desc",
    }
    NOTE_TYPE_MAP: Dict[str, str] = {
        "全部": "_0",
        "视频": "_1",
        "图文": "_2",
    }
    COMMENT_SORT_MAP: Dict[str, str] = {
        "默认": "normal",
        "最新": "latest",
    }
    TIME_RANGE_MAP: Dict[str, int] = {
        "一天内": 1,
        "一周内": 7,
        "半年内": 180,
    }
    MODE_MAP: Dict[str, str] = {
        "按关键词采集笔记": "keyword_notes",
        "按笔记采集评论": "note_comments",
        "按用户信息采集笔记": "user_notes",
    }

    # ---------------- 字段过滤规则（防止输出过长）----------------
    # 评论数据中可过滤的字段
    COMMENT_FILTER_KEYS: set = {
        "hidden",
        "status",
        "show_type",
        "show_tags_v2",
        "translation_strategy",
        "score",
        "friend_liked_msg",
        "collected",
        "at_users",
        "track_id",
        "biz_label",
        "show_tags",
        "downvoted",
        "share_strategy",
        "liked",
        "pictures",
        "sub_comment_cursor",
    }

    # 搜索结果与笔记条目中可过滤的字段
    SEARCH_FILTER_KEYS: set = {
        # 搜索页级
        "cur_cut_number",
        "can_cut",
        "show_single_col",
        "is_broad_query",
        "search_pull_down_opt_exp",
        "search_dqa_new_page_exp",
        "service_status",
        "strategy_info",
        "query_debug_info",
        "request_dqa_instant",
        "query_type",
        "dqa_authorized_user_by_shared",
        # 笔记级
        "has_music",
        "cover_image_index",
        "widgets_context",
        "interaction_area",
        "collected",
        "liked",
        "niced",
        "tag_info",
        "extract_text_enabled",
        "note_attributes",
        "result_from",
        "debug_info_str",
        "geo_info",
        "corner_tag_info",
    }

    # 用户信息数据中可过滤的字段
    USER_INFO_FILTER_KEYS: set = {
        "nboards",
        "collected_notes_num",
        "collected_product_num",
        "red_club_info",
        "tab_public",
        "community_rule_url",
        "identity_deeplink",
        "user_widget_switch",
        "banner_info",
        "zhong_tong_bar_info",
        "red_official_verify_base_info",
        "fstatus",
        "location_jump",
        "ndiscovery",
        "gender",
        "avatar_like_status",
        "recommend_info_icon",
        "seller_info",
        "avatar_pendant",
        "identity_label_migrated",
        "blocked",
        "show_extra_info_button",
    }

    # 用户要求在按作者采集模式下进一步过滤用户信息中的展示性/非核心字段
    USER_INFO_FILTER_KEYS_FOR_USER_NOTES: set = {
        # 1) 顶层 用户信息 可过滤字段（多数位于 data 下）
        "is_recommend_level_illegal",
        "remark_name",
        "level",
        "blocking",
        "hula_tabs",
        "tab_visible",
        "note_num_stat",
        "desc_at_users",
        "college_info",
        "tags",
        "imageb",
        "collected_brand_num",
        "collected_tags_num",
        "collected_movie_num",
        "collected_poi_num",
        "collected_book_num",
        "is_login_user_pro_account",
        "real_name_deep_link",
        "real_name_deep_target",
        "user_role_type",
        "share_info",
        "share_info_v2",
        "default_collection_tab",
        "recommend_info",
        "red_official_verify_content",
        "real_name_info",
        # 额外：数据中不需要的关注数（需求未要求）
        "follows",
    }

    # 原始.data.notes 每条笔记中可过滤的字段集合
    USER_NOTES_ITEM_FILTER_KEYS: set = {
        "last_update_time",
        "advanced_widgets_groups",
        "sticky",
        "ats",
        "recommend",
        "inlikes",
        "infavs",
        # cursor 属于翻页内部指针，不影响我们输出的下一页游标
        "cursor",
        # 笔记中不常用的字段
        "price",
        "level",
        # images_list 子项中不需要的内部键
        "fileid",
        "original",
        "trace_id",
    }

    # 针对原始笔记对象中的子键过滤：images_list 与 user 的部分子字段
    USER_NOTES_ITEM_CHILD_FILTER_MAP: Dict[str, set] = {
        # user 子对象：在笔记列表中只需 userid 与 nickname，移除其它详情（顶层用户信息中可获取完整）
        "user": {"images", "red_official_verify_type", "followed", "fstatus"},
    }

    # 针对搜索笔记的子对象过滤规则
    SEARCH_NOTES_ITEM_CHILD_FILTER_MAP: Dict[str, set] = {
        # user 子对象
        "user": {"images", "red_official_verify_type", "followed", "fstatus"},
        # video_info_v2 子对象
        "video_info_v2": {"capa", "consumer", "image"},
        # video_info_v2.media.video 子对象
        "video": {"hdr_type", "stream_types", "bound", "md5", "drm_type", "opaque1"},
    }

    # 针对视频流信息的过滤规则
    VIDEO_STREAM_ITEM_FILTER_KEYS: set = {
        "audio_codec", "opaque1", "psnr", "vmaf", "ssim", "backup_urls",
        "weight", "sr", "audio_bitrate", "audio_duration", "hdr_type",
        "volume", "default_stream", "avg_bitrate", "fps", "audio_channels",
    }

    # 用户对象（作者/评论用户）中需要过滤的字段
    FILTER_USER_KEYS_FOR_USER_DICT: set = {
        "ai_agent",
        "current_user",
        "level",
        "additional_tags",
        # 搜索/笔记条目中常见的用户子字段
        "track_duration",
        "followed",
        # 其它展示性字段
        "avatar_pendant",
    }

    ERROR_CODE_MAP: Dict[int, str] = {
        0: "成功",
        100: "Token 无效或已失效",
        201: "内容为空（无可用数据）",
        301: "采集失败，请重试",
        302: "超出速率限制",
        303: "超出每日配额",
        400: "参数错误",
        500: "内部服务器错误",
        600: "权限不足",
        601: "余额不足",
    }

    inputs = [
        DropdownInput(
            name="mode",
            display_name="模式",
            info="选择：按关键词采集笔记 / 按笔记采集评论 / 按用户信息采集笔记",
            options=list(MODE_MAP.keys()),
            value="按关键词采集笔记",
            real_time_refresh=True,
            tool_mode=True,
        ),
        DropdownInput(
            name="environment",
            display_name="环境",
            info="中国区或全球区。中国区通常更快，全球区适合境外。",
            options=list(ENV_BASE.keys()),
            value="中国区",
            tool_mode=True,
        ),
        StrInput(
            name="token",
            display_name="Just One API Token",
            info="用于接口鉴权（必填）。为空则使用组件常量 JOA_TOKEN（默认 YOUR_TOKEN 可能导致调用失败），建议填写你的真实 Token。",
            value="",
            tool_mode=True,
        ),

        MultilineInput(
            name="input_value",
            display_name="Text",
            info="Text to be passed as input.",
            tool_mode=True,
        ),
        DropdownInput(
            name="note_type",
            display_name="笔记类型",
            info="枚举：全部/图文/视频",
            options=list(NOTE_TYPE_MAP.keys()),
            value="全部",
            tool_mode=True,
        ),
        DropdownInput(
            name="sort",
            display_name="排序类型",
            info="枚举：综合、最热、最新（最多评论/最多收藏仅作客户端参考，实际按综合请求）",
            options=list(SEARCH_SORT_MAP.keys()),
            value="综合",
            tool_mode=True,
        ),
        IntInput(
            name="start_page",
            display_name="开始页",
            info="页码从 1 开始，最小为 1",
            value=1,
            tool_mode=True,
        ),
        IntInput(
            name="end_page",
            display_name="结束页",
            info="整数范围，默认 1",
            value=1,
            tool_mode=True,
        ),
        DropdownInput(
            name="time_range",
            display_name="时间范围",
            info="一天内 / 一周内 / 半年内（对应 v2 的 noteTime 参数；结果中仅标注是否在范围内）",
            options=list(TIME_RANGE_MAP.keys()),
            value="一天内",
            tool_mode=True,
        ),
        BoolInput(
            name="include_author_detail",
            display_name="作者详细信息",
            info="开启后为每条笔记追加作者详情（User Info v4/v3）",
            value=False,
            tool_mode=True,
        ),
        # 已移除：笔记详情开关（不再调用 v7/v3 详情接口）

        MessageTextInput(
            name="note_input",
            display_name="笔记链接或ID",
            info="支持输入 https://www.xiaohongshu.com/explore/<id> 或直接笔记ID",
            value="",
            tool_mode=True,
        ),
        DropdownInput(
            name="comment_mode",
            display_name="采集模式",
            info="默认/最新（接口排序；仅使用 Note Comment v2，不调用详情接口）",
            options=["默认", "最新"],
            value="默认",
            tool_mode=True,
        ),
        BoolInput(
            name="include_sub_comments",
            display_name="是否采集二级评论",
            info="开启后按评论ID拉取二级回复（Note Sub Comment v2）",
            value=False,
            tool_mode=True,
        ),
        # 评论模式不分页：移除 comments_last_cursor 输入

        StrInput(
            name="xhs_user_id",
            display_name="用户 UID",
            info="用于拉取该用户的笔记列表（User Note List v4/v2）",
            value="",
            tool_mode=True,
        ),
        IntInput(
            name="user_notes_pages",
            display_name="采集页数",
            info="最多采集的页数（基于 has_more/cursor 分页，默认 1 页）",
            value=1,
            tool_mode=True,
        ),
        # 已移除：用户笔记强制详情开关（仅使用列表 desc）
    ]

    outputs = [
        Output(display_name="统一JSON输出", name="output", method="build_output"),
    ]

    _metrics: Dict[str, Any] = {}

    def _base_url(self) -> str:
        return self.ENV_BASE.get(getattr(self, "environment", "中国区") or "中国区", self.ENV_BASE["中国区"])

    @staticmethod
    def _mask_token(token: Optional[str]) -> str:
        t = token or ""
        if len(t) <= 8:
            return "***"
        return f"{t[:3]}***{t[-4:]}"

    def _http_get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url()}{path}"
        token = getattr(self, "token", None) or self.JOA_TOKEN
        query = {"token": token, **{k: v for k, v in params.items() if v not in (None, "")}}

        def classify_error(http_status: int | None, body: Dict[str, Any] | None) -> str:
            code = None
            msg = ""
            if isinstance(body, dict):
                code = body.get("code")
                msg = str(body.get("message") or body.get("msg") or "")
            if http_status is not None:
                if http_status in (401, 403):
                    return "auth_error"
                if http_status == 429:
                    return "rate_limit"
                if http_status >= 500:
                    return "server_error"
                if http_status >= 400:
                    return "http_error"
            # 业务码细分：100 表示 Token 未激活/失效，按鉴权错误处理
            if isinstance(code, int) and code == 100:
                return "auth_error"
            # 文案包含 TOKEN INVALID/UNACTIVATE 也视为鉴权错误
            up = msg.upper()
            if "TOKEN" in up and ("INVALID" in up or "UNACTIVATE" in up):
                return "auth_error"
            if isinstance(code, int) and code != 0:
                return "api_error"
            return ""

        # 每次请求前的固定等待（不暴露到前台选项）
        try:
            pre_delay_ms = int(getattr(self, "REQUEST_PRE_DELAY_MS", 0) or 0)
        except Exception:
            pre_delay_ms = 0
        if pre_delay_ms > 0:
            time.sleep(pre_delay_ms / 1000.0)

        attempts = max(1, int(getattr(self, "REQUEST_RETRY_ATTEMPTS", 1) or 1))
        timeout_s = max(1, int(getattr(self, "REQUEST_TIMEOUT_SECONDS", 60) or 60))
        backoff_base_ms = max(0, int(getattr(self, "REQUEST_RETRY_BACKOFF_BASE_MS", 500) or 500))
        jitter_ms_max = max(0, int(getattr(self, "REQUEST_RETRY_BACKOFF_JITTER_MS", 300) or 300))

        last_error_payload: Optional[Dict[str, Any]] = None
        last_http_status: Optional[int] = None

        for attempt_idx in range(1, attempts + 1):
            start = time.perf_counter()
            try:
                resp = requests.get(url, params=query, timeout=timeout_s)
                duration_ms = int((time.perf_counter() - start) * 1000)
                status = resp.status_code
                try:
                    body = resp.json()
                except json.JSONDecodeError:
                    body = None

                self._metrics.setdefault("request_durations", {}).setdefault(path, []).append(duration_ms)

                # 提前处理 body，注入中文信息
                if isinstance(body, dict):
                    code = body.get("code")
                    if isinstance(code, int) and code in self.ERROR_CODE_MAP:
                        body["message_cn"] = self.ERROR_CODE_MAP[code]

                if isinstance(body, dict) and body.get("code") == 0:
                    return body

                error_type = classify_error(status, body if isinstance(body, dict) else None)
                debug_req = {
                    "path": path,
                    "url": resp.url,
                    "环境": getattr(self, "environment", "中国区"),
                    "params": {**{k: v for k, v in params.items() if v not in (None, "")}, "token": self._mask_token(token)},
                    "http_status": status,
                    "duration_ms": duration_ms,
                    "attempt": attempt_idx,
                }

                # 仅在网络/服务端错误/限流/无效JSON时重试；鉴权/业务错误不重试
                should_retry = error_type in ("server_error", "rate_limit") or (status is not None and (status >= 500 or status == 429))
                if body is None:
                    should_retry = True

                if should_retry and attempt_idx < attempts:
                    # 指数退避 + 随机抖动
                    jitter = random.randint(0, jitter_ms_max) if jitter_ms_max > 0 else 0
                    backoff_ms = backoff_base_ms * (2 ** (attempt_idx - 1)) + jitter
                    time.sleep(backoff_ms / 1000.0)
                    continue

                # 不重试或已到最大次数：返回错误结构（保持原格式）
                if isinstance(body, dict):
                    return {**body, "error": {"type": error_type, **debug_req}}
                else:
                    return {
                        "code": -1,
                        "message": f"invalid json or http error (status={status})",
                        "message_cn": "无效的JSON响应或HTTP错误",
                        "data": None,
                        "error": {"type": error_type or "invalid_json", **debug_req},
                    }

            except requests.RequestException as e:
                duration_ms = int((time.perf_counter() - start) * 1000)
                self._metrics.setdefault("request_durations", {}).setdefault(path, []).append(duration_ms)
                debug_req = {
                    "path": path,
                    "url": f"{url}",
                    "环境": getattr(self, "environment", "中国区"),
                    "params": {**{k: v for k, v in params.items() if v not in (None, "")}, "token": self._mask_token(token)},
                    "http_status": None,
                    "duration_ms": duration_ms,
                    "attempt": attempt_idx,
                }

                if attempt_idx < attempts:
                    jitter = random.randint(0, jitter_ms_max) if jitter_ms_max > 0 else 0
                    backoff_ms = backoff_base_ms * (2 ** (attempt_idx - 1)) + jitter
                    time.sleep(backoff_ms / 1000.0)
                    continue

                return {
                    "code": -1,
                    "message": f"request error: {e}",
                    "message_cn": "网络请求异常",
                    "data": None,
                    "error": {"type": "network_error", **debug_req},
                }

    def _build_params(self, required: Dict[str, Any], optional: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        通用参数构造器（不含 token）：
        - 必填：直接写入（上层负责确保非空）；
        - 选填：过滤 None、空字符串或仅空白；
        返回仅包含有效字段的字典，保证不会把空的选填字段拼进请求。
        """
        params: Dict[str, Any] = {}
        # 必填字段按原样写入（由调用方/上层确保非空）
        for k, v in (required or {}).items():
            params[k] = v
        # 选填字段过滤空值
        if optional:
            for k, v in optional.items():
                if v is None:
                    continue
                if isinstance(v, str) and v.strip() == "":
                    continue
                params[k] = v
        return params

    @staticmethod
    def _note_url(note_id: str) -> str:
        return f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""

    

    @staticmethod
    def _extract_note_desc(detail_resp: Dict[str, Any], fallback_note: Optional[Dict[str, Any]] = None) -> Optional[str]:
        try:
            d = detail_resp.get("data") or {}
            items = d.get("note_list") or d.get("items") or []
            if isinstance(items, list) and items:
                first = items[0] or {}
                desc = first.get("desc")
                if isinstance(desc, str) and desc.strip():
                    return desc
            desc2 = d.get("desc")
            if isinstance(desc2, str) and desc2.strip():
                return desc2
        except Exception:
            pass
        if isinstance(fallback_note, dict):
            txt = fallback_note.get("desc") or fallback_note.get("display_title")
            if isinstance(txt, str) and txt.strip():
                return txt
        return None

    @staticmethod
    def _ensure_note_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        将搜索结果中的条目统一规整为“笔记对象”。
        - 常见结构：{"model_type": "note", "note": { ..真实笔记.. }}
        - 广告结构：{"model_type": "ads", "ads": { "model_type": "note", "note": { ..真实笔记.. } }}
        - 少数旧结构：顶层直接就是笔记对象（无 model_type / 无嵌套）

        之前只处理了 ads 且误取了顶层 note，导致提取失败；同时对 "model_type": "note" 的嵌套未展开，
        造成标题/ID/互动数据为空。这里统一展开两类嵌套，兜底返回原始对象。
        """
        try:
            mt = item.get("model_type")
            # 广告：真实笔记在 ads.note
            if mt == "ads":
                ads = item.get("ads") or {}
                if isinstance(ads, dict):
                    nested = ads.get("note") or (ads.get("payload", {}) if isinstance(ads.get("payload"), dict) else {}).get("note")
                    if isinstance(nested, dict) and nested:
                        return nested
                # 兜底：有些返回可能把 note 混在顶层（极少数情况）
                return item.get("note") or {}

            # 普通笔记：真实笔记在 item.note
            if mt == "note":
                return item.get("note") or item

            # 其它情况：如果存在嵌套 note 字段也尝试展开
            if isinstance(item.get("note"), dict):
                return item.get("note")

            return item
        except Exception:
            return item

    @staticmethod
    def _extract_cover(note: Dict[str, Any]) -> Optional[str]:
        vi = note.get("video_info_v2") or {}
        image = vi.get("image") or {}
        first = image.get("first_frame") or image.get("thumbnail")
        if isinstance(first, str) and first:
            return first
        images = note.get("images_list") or note.get("imagesList") or []
        if isinstance(images, list) and images:
            img0 = images[0] or {}
            return img0.get("url_size_large") or img0.get("url")
        return None

    @staticmethod
    def _extract_video_master(note: Dict[str, Any]) -> Optional[str]:
        vi = note.get("video_info_v2") or {}
        media = vi.get("media") or {}
        stream = media.get("stream") or {}
        for codec in ("h264", "h265"):
            arr = stream.get(codec) or []
            if isinstance(arr, list) and arr:
                master = None
                for s in arr:
                    if s.get("default_stream") == 1:
                        master = s.get("master_url")
                        break
                if not master:
                    master = arr[0].get("master_url")
                if master:
                    return master
        images = note.get("images_list") or []
        for img in images:
            live = (img or {}).get("live_photo") or {}
            media2 = live.get("media") or {}
            stream2 = media2.get("stream") or {}
            for codec in ("h265", "h264"):
                arr2 = stream2.get(codec) or []
                if isinstance(arr2, list) and arr2:
                    return arr2[0].get("master_url")
        return None

    @staticmethod
    def _extract_all_covers(note: Dict[str, Any]) -> List[str]:
        """
        收集全部可能的封面图：
        - 视频：video_info_v2.image.first_frame 与 image.thumbnail
        - 图文：images_list[*].url_size_large 与 url
        保持去重和原始顺序。
        """
        out: List[str] = []
        seen = set()
        try:
            vi = note.get("video_info_v2") or {}
            image = vi.get("image") or {}
            for key in ("first_frame", "thumbnail"):
                val = image.get(key)
                if isinstance(val, str) and val and val not in seen:
                    seen.add(val)
                    out.append(val)
            images = note.get("images_list") or note.get("imagesList") or []
            if isinstance(images, list):
                for img in images:
                    if not isinstance(img, dict):
                        continue
                    for k in ("url_size_large", "url"):
                        u = img.get(k)
                        if isinstance(u, str) and u and u not in seen:
                            seen.add(u)
                            out.append(u)
        except Exception:
            pass
        return out

    @staticmethod
    def _extract_all_video_masters(note: Dict[str, Any]) -> List[str]:
        """
        收集全部可能的视频 master_url：
        - video_info_v2.media.stream.h264/h265[*].master_url（含默认流与各分辨率）
        - images_list[*].live_photo.media.stream.h264/h265[*].master_url
        保持去重和原始顺序。
        """
        out: List[str] = []
        seen = set()
        try:
            vi = note.get("video_info_v2") or {}
            media = vi.get("media") or {}
            stream = media.get("stream") or {}
            for codec in ("h264", "h265"):
                arr = stream.get(codec) or []
                if isinstance(arr, list):
                    for it in arr:
                        if not isinstance(it, dict):
                            continue
                        url = it.get("master_url")
                        if isinstance(url, str) and url and url not in seen:
                            seen.add(url)
                            out.append(url)
            images = note.get("images_list") or note.get("imagesList") or []
            if isinstance(images, list):
                for img in images:
                    lp = (img or {}).get("live_photo") or {}
                    media2 = (lp or {}).get("media") or {}
                    stream2 = (media2 or {}).get("stream") or {}
                    for codec in ("h264", "h265"):
                        arr2 = stream2.get(codec) or []
                        if isinstance(arr2, list):
                            for it in arr2:
                                if not isinstance(it, dict):
                                    continue
                                url2 = it.get("master_url")
                                if isinstance(url2, str) and url2 and url2 not in seen:
                                    seen.add(url2)
                                    out.append(url2)
        except Exception:
            pass
        return out

    @staticmethod
    def _extract_tags_from_text(text: Optional[str]) -> List[str]:
        if not isinstance(text, str) or not text:
            return []
        tags = re.findall(r"#([^#]+)#", text)
        return [t.strip() for t in tags if t.strip()]

    @staticmethod
    def _is_official_verified(user: Dict[str, Any]) -> bool:
        try:
            vt = user.get("red_official_verify_type")
            vf = user.get("red_official_verified")
            if isinstance(vf, bool):
                return vf
            return bool(vt) and vt != 0
        except Exception:
            return False

    @staticmethod
    def _calc_author_liked_collected(user_info_resp: Dict[str, Any]) -> Optional[int]:
        try:
            data = user_info_resp.get("data") or {}
            inters = data.get("interactions") or []
            if isinstance(inters, list):
                for it in inters:
                    if (it or {}).get("type") == "interaction":
                        cnt = it.get("count")
                        if isinstance(cnt, int):
                            return cnt
            liked = data.get("liked") or (data.get("note_num_stat") or {}).get("liked")
            collected = data.get("collected") or (data.get("note_num_stat") or {}).get("collected")
            if isinstance(liked, int) and isinstance(collected, int):
                return liked + collected
        except Exception:
            pass
        return None

    @staticmethod
    def _author_profile_link(user_info_resp: Dict[str, Any]) -> Optional[str]:
        try:
            data = user_info_resp.get("data") or {}
            share = data.get("share_link")
            if isinstance(share, str) and share:
                return share
            userid = data.get("userid") or data.get("user_id")
            if isinstance(userid, str) and userid:
                return f"https://www.xiaohongshu.com/user/profile/{userid}"
        except Exception:
            pass
        return None

    def _get_note_comments_v2(self, note_id: str, sort: str, last_cursor: Optional[str] = None) -> Dict[str, Any]:
        params = self._build_params(
            required={"noteId": note_id},
            optional={"sort": sort, "lastCursor": last_cursor},
        )
        resp = self._http_get(self.PATHS["note_comment_v2"], params)
        self._metrics.setdefault("version_choice", []).append({"api": "note_comment", "prefer": "v2", "result_code": resp.get("code")})
        return resp

    # 已移除 v4 评论接口，实现仅保留 v2 评论采集

    def _get_note_sub_comments(self, note_id: str, comment_id: str, last_cursor: Optional[str] = None) -> Dict[str, Any]:
        params = self._build_params(
            required={"noteId": note_id, "commentId": comment_id},
            optional={"lastCursor": last_cursor},
        )
        return self._http_get(self.PATHS["note_sub_comment_v2"], params)

    def _get_user_notes(self, user_id: str, last_cursor: Optional[str] = None) -> Dict[str, Any]:
        params = self._build_params(required={"userId": user_id}, optional={"lastCursor": last_cursor})
        resp4 = self._http_get(self.PATHS["user_note_list_v4"], params)
        self._metrics.setdefault("version_choice", []).append({"api": "user_note_list", "prefer": "v4", "result_code": resp4.get("code")})
        if resp4.get("code") == 0:
            return resp4
        resp2 = self._http_get(self.PATHS["user_note_list_v2"], params)
        self._metrics.setdefault("version_choice", []).append({"api": "user_note_list", "fallback": "v2", "result_code": resp2.get("code")})
        return resp2

    def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        params = self._build_params(required={"userId": user_id})
        resp4 = self._http_get(self.PATHS["user_info_v4"], params)
        self._metrics.setdefault("version_choice", []).append({"api": "user_info", "prefer": "v4", "result_code": resp4.get("code")})
        if resp4.get("code") == 0:
            return resp4
        resp3 = self._http_get(self.PATHS["user_info_v3"], params)
        self._metrics.setdefault("version_choice", []).append({"api": "user_info", "fallback": "v3", "result_code": resp3.get("code")})
        return resp3

    def _search_notes(self, keyword: str, page: int, sort: str, note_type: str, note_time: Optional[str] = None) -> Dict[str, Any]:
        """
        关键词搜索：仅使用 v2（search-note/v2），不再调用 v3。
        支持字段：keyword、page、sort、noteType，以及 v2 独有的 noteTime（一天内/一周内/半年内）。
        """
        params_v2 = self._build_params(
            required={"keyword": keyword, "page": page, "sort": sort, "noteType": note_type},
            optional={"noteTime": note_time} if note_time else None,
        )
        resp2 = self._http_get(self.PATHS["search_note_v2"], params_v2)
        self._metrics.setdefault("version_choice", []).append({"api": "search_note", "prefer": "v2", "result_code": resp2.get("code")})
        return resp2

    @staticmethod
    def _parse_note_id(note_input: str) -> str:
        note_input = (note_input or "").strip()
        if not note_input:
            return ""
        m = re.search(r"explore/([a-zA-Z0-9]+)", note_input)
        if m:
            return m.group(1)
        if re.fullmatch(r"[a-zA-Z0-9]+", note_input):
            return note_input
        return ""

    @staticmethod
    def _now_seconds() -> int:
        return int(time.time())

    @staticmethod
    def _normalize_ts(ts: Any) -> Optional[int]:
        try:
            if ts is None:
                return None
            if isinstance(ts, int):
                if ts > 10_000_000_000:
                    return ts // 1000
                return ts
            if isinstance(ts, str) and ts.isdigit():
                val = int(ts)
                if val > 10_000_000_000:
                    return val // 1000
                return val
        except Exception:
            return None
        return None

    def _in_time_range(self, ts: Optional[int], days: int) -> bool:
        if ts is None:
            return True
        now = self._now_seconds()
        return (now - ts) <= days * 24 * 3600

    @staticmethod
    def _is_valid_user_id(user_id: str) -> bool:
        # 小红书 UID 通常为 24 位十六进制字符串（小写），例如 636519f2000000001f019e57
        # 使用更严格的校验以避免误判
        return bool(re.fullmatch(r"[0-9a-f]{24}", user_id or ""))

    @staticmethod
    def _clean_user_id(user_id: str) -> str:
        """
        清洗用户 UID：去除前后空格，保持与校验逻辑兼容。
        如传入非字符串或异常，返回空字符串以便上层处理。
        """
        try:
            return (user_id or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _get_keyword_notes_parser():
        """
        兼容性获取关键词解析器：
        - 优先局部导入 keyword_notes_parser.KeywordNotesParser，避免模块路径差异导致的 AttributeError；
        - 若导入失败，回退到文件顶部的 KeywordNotesParser 变量（可能为 None）；
        - 始终返回类或 None，调用方需判空后再使用。
        """
        try:
            from keyword_notes_parser import KeywordNotesParser as _Parser
            return _Parser
        except Exception:
            try:
                # 使用顶部 try/except 设置的同名变量（若存在）
                return KeywordNotesParser  # type: ignore[name-defined]
            except Exception:
                return None

    # 递归过滤工具：移除字典/列表中不需要的键
    def _filter_keys_recursive(
        self,
        obj: Any,
        remove_keys: set,
        remove_children_by_parent: Optional[Dict[str, set]] = None,
        remove_key_prefixes: Optional[set] = None,
    ) -> Any:
        try:
            if isinstance(obj, dict):
                new_obj: Dict[str, Any] = {}
                for k, v in obj.items():
                    # 删除指定键或匹配前缀的键
                    if k in remove_keys:
                        continue
                    if remove_key_prefixes and any(str(k).startswith(pref) for pref in remove_key_prefixes):
                        continue
                    new_v = self._filter_keys_recursive(v, remove_keys, remove_children_by_parent, remove_key_prefixes)
                    # 如需对子层做额外过滤（例如 user 下的特定字段）
                    if isinstance(new_v, dict) and remove_children_by_parent and k in remove_children_by_parent:
                        for ck in remove_children_by_parent.get(k, set()):
                            if ck in new_v:
                                new_v.pop(ck, None)
                    new_obj[k] = new_v
                return new_obj
            elif isinstance(obj, list):
                return [self._filter_keys_recursive(i, remove_keys, remove_children_by_parent, remove_key_prefixes) for i in obj]
            else:
                return obj
        except Exception:
            return obj

    def _filter_dict_keys(
        self,
        d: Any,
        remove_keys: Optional[set] = None,
        remove_key_prefixes: Optional[set] = None,
    ) -> Any:
        """
        精简字典的便捷方法：
        - 从给定字典中删除指定键（remove_keys）;
        - 删除以某些前缀开头的键（remove_key_prefixes）。
        返回处理后的同一个对象，便于就地修改。
        """
        try:
            if not isinstance(d, dict):
                return d
            if remove_keys:
                for k in list(d.keys()):
                    if k in remove_keys:
                        d.pop(k, None)
            if remove_key_prefixes:
                for k in list(d.keys()):
                    if any(str(k).startswith(pref) for pref in remove_key_prefixes):
                        d.pop(k, None)
            return d
        except Exception:
            return d

    def _filter_user_basic(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """过滤用户对象中的展示性/非核心字段。"""
        return self._filter_keys_recursive(user or {}, self.FILTER_USER_KEYS_FOR_USER_DICT)

    def _compact_user_for_search(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        搜索结果中的用户对象精简：
        - 仅保留昵称、红书号(red_id)、userid（用于生成主页链接）；
        - 保留官方认证布尔值 official_verified（由 red_official_verify_type 推断）；
        - 其余字段全部移除。
        """
        try:
            u = user or {}
            allowed = {
                "userid": u.get("userid") or u.get("userId") or u.get("id"),
                "nickname": u.get("nickname"),
                "red_id": u.get("red_id") or u.get("redId") or u.get("redID"),
            }
            # 官方认证
            try:
                allowed["official_verified"] = bool((u.get("red_official_verify_type") or u.get("official_verify_type")) == 1)
            except Exception:
                allowed["official_verified"] = False
            return {k: v for k, v in allowed.items() if v not in (None, "")}
        except Exception:
            return {}

    def _compact_images_list(self, images_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        精简 images_list：
        - 对每个元素仅保留一个图片/视频 URL：优先 url，其次 url_size_large；
        - 若存在 live_photo.media.stream.master_url，则保留该字段（其它统计/码率/备份等全部删除）。
        """
        compacted: List[Dict[str, Any]] = []
        for img in images_list or []:
            try:
                url = (
                    img.get("url")
                    or img.get("url_size_large")
                    or img.get("imgUrl")
                    or img.get("originUrl")
                )
                entry: Dict[str, Any] = {}
                if url:
                    entry["url"] = url
                # 保留主视频地址（若存在）
                try:
                    master_url = (
                        (((img.get("live_photo") or {}).get("media") or {}).get("stream") or {}).get("master_url")
                    )
                    if master_url:
                        entry.setdefault("live_photo", {}).setdefault("media", {}).setdefault("stream", {})["master_url"] = master_url
                except Exception:
                    pass
                if entry:
                    compacted.append(entry)
            except Exception:
                # 异常情况下保留一个空对象以占位，避免前端解析错误
                compacted.append({})
        return compacted

    def _compact_search_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        """
        精简搜索结果中的笔记对象：
        - 删除与展示无关的冗余字段（活动、挑战、导购、广告、推荐、交互等）；
        - images_list 仅保留一个 URL + 可选的 master_url；
        - user 仅保留 userid/nickname/red_id/official_verified。
        """
        remove_keys = set().union(
            {
                # 指定删除的笔记级冗余字段
                "advanced_widgets_groups",
                "note_nice_guide",
                "next_note_guide",
                "product_review",
                "goods_card_v2",
                "rec_next_infos",
                "related_recommend",
                "related_search",
                "poi",
                "brand",
                "music",
                "soundtrack",
                "bar",
                "vote",
                "interact",
                "bullet_comment_lead",
                "search_box",
                "biz_id",
                "biz_name",
                "userLevel",
                "track_duration",
                "tracking_info",
                "experiment_info",
                # 已在 SEARCH_FILTER_KEYS 中的常见展示性字段（重复无妨）
                "widgets_context",
                "interaction_area",
                "result_from",
                "debug_info_str",
                "corner_tag_info",
            }
        )

        remove_prefixes = {"ads_", "ad_", "cooperate_", "guide_", "widgets_", "super_activity"}

        # 先做通用键删除
        pruned = self._filter_keys_recursive(note or {}, remove_keys, remove_key_prefixes=remove_prefixes)

        # 精简用户
        try:
            if isinstance(pruned.get("user"), dict):
                pruned["user"] = self._compact_user_for_search(pruned.get("user") or {})
        except Exception:
            pass

        # 精简 images_list
        try:
            imgs = pruned.get("images_list")
            if isinstance(imgs, list):
                pruned["images_list"] = self._compact_images_list(imgs)
        except Exception:
            pass

        return pruned

    def _compact_search_response(self, resp: Dict[str, Any]) -> Dict[str, Any]:
        """
        针对 search-note v2 的响应进行整体瘦身：
        - 移除 data.query_intent 整段；
        - items[].model_type 删除；
        - 对 items 中的笔记对象进行精简（images_list / user / 冗余键 / 视频元数据）。
        """
        try:
            # 先做一轮全局过滤（顶层与笔记级别常见冗余）
            base_filtered = self._filter_keys_recursive(
                resp or {},
                self.SEARCH_FILTER_KEYS.union({"query_intent", "model_type"}),
                remove_key_prefixes={"ads_", "ad_", "cooperate_", "guide_", "widgets_", "super_activity"},
            )

            data = base_filtered.get("data") if isinstance(base_filtered, dict) else None
            if isinstance(data, dict):
                items = data.get("items") or data.get("list") or []
                new_items: List[Any] = []
                for it in items:
                    try:
                        # 有些结构为 {model_type: 'note', note: {...}}
                        note_obj = it.get("note") if isinstance(it, dict) else None
                        if isinstance(note_obj, dict):
                            compact_note = self._compact_search_note(note_obj)
                            # 去除包裹层，仅保留 note 内容
                            new_items.append({"note": compact_note})
                        elif isinstance(it, dict):
                            # 若没有子键 note，则直接按 note 结构处理
                            new_items.append(self._compact_search_note(it))
                        else:
                            new_items.append(it)
                    except Exception:
                        new_items.append(it)
                # 深度过滤（作用在每条笔记的 note 对象上）
                for idx, item in enumerate(new_items):
                    note = item.get("note") if isinstance(item, dict) else item
                    if not isinstance(note, dict):
                        continue

                    # 过滤笔记作者信息（仅保留 userid/nickname/red_id/official_verified）
                    try:
                        if isinstance(note.get("user"), dict):
                            note["user"] = self._compact_user_for_search(note.get("user") or {})
                    except Exception:
                        pass

                    # 过滤视频信息（仅保留必要的播放信息）
                    try:
                        video_info = note.get("video_info_v2")
                        if isinstance(video_info, dict):
                            self._filter_dict_keys(video_info, self.SEARCH_NOTES_ITEM_CHILD_FILTER_MAP.get("video_info_v2"))
                            media = video_info.get("media")
                            if isinstance(media, dict):
                                # 过滤 video 技术参数
                                self._filter_dict_keys(media.get("video", {}), self.SEARCH_NOTES_ITEM_CHILD_FILTER_MAP.get("video"))
                                # 过滤 stream 列表中的冗余指标
                                streams = media.get("stream")
                                if isinstance(streams, list):
                                    for s in streams:
                                        self._filter_dict_keys(s, self.VIDEO_STREAM_ITEM_FILTER_KEYS)
                    except Exception:
                        pass

                    # 写回 note
                    if isinstance(item, dict) and "note" in item:
                        item["note"] = note
                        new_items[idx] = item
                    else:
                        new_items[idx] = note

                data["items"] = new_items
            return base_filtered
        except Exception:
            # 若出现异常，返回原始 resp，避免影响功能
            return resp

    def _format_comment_item(self, c: Dict[str, Any], note_author_id: Optional[str] = None, level: str = "根评论") -> Dict[str, Any]:
        # 过滤评论中的用户字段，减小输出体积
        user_obj = self._filter_user_basic(c.get("user") or {})
        cm = {
            "评论ID": c.get("id"),
            "用户": user_obj,
            "昵称": user_obj.get("nickname"),
            "小红书号": user_obj.get("red_id"),
            "评论内容": c.get("content"),
            "点赞数": c.get("like_count") or c.get("likedCount") or c.get("likeCount"),
            "发布时间": c.get("time") or c.get("publishTime"),
            "发布地点": c.get("location") or "",
            "二级评论数": c.get("sub_comment_count"),
            "评论级别": level,
            "作者ID": note_author_id,
            "是否官方认证": self._is_official_verified(user_obj),
        }
        if 'target_comment' in c and c['target_comment']:
            target_user = self._filter_user_basic(c['target_comment'].get('user', {}) or {})
            cm['回复目标'] = {
                '评论ID': c['target_comment'].get('id'),
                '用户': target_user,
                '昵称': target_user.get('nickname'),
                '内容': c['target_comment'].get('content'),
            }

        try:
            verified_type = user_obj.get("red_official_verify_type")
            cm.setdefault("用户", {})["official_verified"] = bool(verified_type == 1)
        except Exception:
            pass
        return cm

    def build_output(self) -> Data:
        self._metrics = {"request_durations": {}, "version_choice": []}

        mode_label = getattr(self, "mode", "按关键词采集笔记")
        mode_internal = self.MODE_MAP.get(mode_label, "keyword_notes")
        base_url = self._base_url()
        token_val = getattr(self, "token", None) or self.JOA_TOKEN

        # 不再支持“笔记详情(正文)”及“用户笔记强制详情”开关：所有模式统一使用列表/评论接口

        # 在输出开头明确展示用户选择的模式（你的诉求）
        result: Dict[str, Any] = {
            "模式": mode_label,
            "环境": getattr(self, "environment", "中国区"),
            "基础地址": base_url,
            "数据": [],
            "meta": {"请求耗时": {}, "版本选择": [], "统计": {}},
        }
        # 关键词模式不再进行详情调用统计，保持输出简洁稳健

        # 早期校验 Token，避免不必要的网络请求
        if (not token_val) or (str(token_val).strip() == "") or (str(token_val).strip() == "YOUR_TOKEN"):
            result["错误"] = {
                "类型": "missing_token",
                "消息": "Token 未配置或为默认值（YOUR_TOKEN）。请在组件输入中填写你的 Just One API Token；如仍提示 TOKEN INVALID/UNACTIVATE，请联系激活或尝试切换环境为‘全球区’。",
            }
            return Data(data=result)

        if mode_internal == "keyword_notes":
            # 仅保留最基本的请求与过滤，杜绝一切可能出错的复杂逻辑
            input_text: str = getattr(self, "input_value", "")
            sort_label: str = getattr(self, "sort", "综合")
            sort_internal: str = self.SEARCH_SORT_MAP.get(sort_label, "general")
            # 将“最多评论/最多收藏”映射为服务端可识别的排序，其余原样传递
            if sort_internal == "client_comments_desc":
                api_sort: str = "comment_descending"
            elif sort_internal == "client_collected_desc":
                api_sort = "collect_descending"
            else:
                api_sort = sort_internal
            note_type_label: str = getattr(self, "note_type", "全部")
            note_type: str = self.NOTE_TYPE_MAP.get(note_type_label, "_0")
            start_page: int = max(1, int(getattr(self, "start_page", 1) or 1))
            end_page: int = max(1, int(getattr(self, "end_page", 1) or 1))
            time_range_label: str = getattr(self, "time_range", "一天内")

            if not input_text:
                result["错误"] = {"类型": "input_error", "消息": "缺少输入文本，请填写 'Text'"}
                return Data(data=result)

            for p in range(min(start_page, end_page), max(start_page, end_page) + 1):
                # 关键词搜索：仅使用 V2，严格传递 token/keyword/page/sort/noteType/noteTime
                resp = self._search_notes(input_text, p, api_sort, note_type, time_range_label)
                # 输出瘦身：移除请求信息，只保留经过裁剪的原始响应
                page_block: Dict[str, Any] = {
                    "页码": p,
                    "原始": self._compact_search_response(resp),
                }
                result["数据"].append(page_block)

        elif mode_internal == "note_comments":
            note_input: str = getattr(self, "note_input", "")
            note_id: str = self._parse_note_id(note_input)
            comment_mode: str = getattr(self, "comment_mode", "默认")
            include_sub_comments: bool = bool(getattr(self, "include_sub_comments", False))

            if not note_id:
                result["错误"] = {"类型": "input_error", "消息": "缺少笔记ID或链接，请填写 '笔记链接或ID'", "调试": {"原始输入": note_input}}
                return Data(data=result)

            sort_internal = self.COMMENT_SORT_MAP.get(comment_mode, "normal")
            
            # ---一级评论分页采集 (最多2页)---
            comments: List[Dict[str, Any]] = []
            note_author_id = None
            l1_last_cursor = None
            l1_has_more = True
            l1_raw_responses = []

            for _ in range(2):
                if not l1_has_more and _ > 0:
                    break
                
                resp = self._get_note_comments_v2(note_id, sort_internal, l1_last_cursor)
                # 一级评论原始响应进行过滤
                l1_raw_responses.append(self._filter_keys_recursive(resp, self.COMMENT_FILTER_KEYS))

                if resp.get("code") == 0 and isinstance(resp.get("data"), dict):
                    data = resp["data"]
                    items = data.get("comments") or data.get("list") or data.get("items") or []
                    if note_author_id is None:
                        note_author_id = data.get("user_id")

                    for c in items:
                        comments.append(self._format_comment_item(c, note_author_id, "根评论"))

                    l1_has_more = data.get("has_more", False)
                    l1_last_cursor = data.get("cursor")
                else:
                    break # API 失败则中止

            block: Dict[str, Any] = {
                "笔记ID": note_id,
                "原始": l1_raw_responses, # 存储所有一级评论的原始响应
                "评论": [],
                "请求信息": {
                    "环境": getattr(self, "environment", "中国区"),
                    "评论": {
                        "path_v2": self.PATHS["note_comment_v2"],
                        "url_v2": f"{base_url}{self.PATHS['note_comment_v2']}",
                        "params_v2": {
                            **self._build_params(
                                required={"noteId": note_id},
                                optional={"sort": sort_internal, "lastCursor": l1_last_cursor},
                            ),
                            "token": self._mask_token(token_val),
                        },
                    }
                }
            }

            # ---二级评论分页采集 (对每个一级评论，最多采集2页)---
            if include_sub_comments and comments:
                for c in comments:
                    cid = c.get("评论ID")
                    if not (cid and c.get("二级评论数", 0) > 0):
                        continue
                    
                    c["二级评论"] = []
                    l2_last_cursor = None
                    l2_has_more = True

                    for _ in range(2):
                        if not l2_has_more and _ > 0:
                            break
                        
                        sub_resp = self._get_note_sub_comments(note_id, cid, l2_last_cursor)
                        # 二级评论原始响应过滤
                        c.setdefault("二级评论原始响应", []).append(self._filter_keys_recursive(sub_resp, self.COMMENT_FILTER_KEYS))
                        
                        if sub_resp.get("code") == 0 and isinstance(sub_resp.get("data"), dict):
                            data = sub_resp["data"]
                            sub_items = data.get("comments", [])
                            for sc in sub_items:
                                c["二级评论"].append(self._format_comment_item(sc, note_author_id, "二级评论"))
                            
                            l2_has_more = data.get("has_more", False)
                            l2_last_cursor = data.get("cursor")
                        else:
                            break # API 失败则中止

            block["评论"] = comments
            result["数据"].append(block)

        elif mode_internal == "user_notes":
            # 思考：这里我们将用户笔记改为“基于 cursor 的多页采集”，并在每页缺失正文时按需调用详情；整体结构与本组件其它模式保持一致，避免格式突变。
            raw_user_id: str = (getattr(self, "xhs_user_id", "") or "")
            user_id: str = self._clean_user_id(raw_user_id)
            last_cursor: Optional[str] = None
            max_pages: int = max(1, int(getattr(self, "user_notes_pages", 1) or 1))
            # 不再调用详情接口：正文仅使用列表字段 desc（缺失置为 None）。

            if not user_id:
                result["错误"] = {"类型": "input_error", "消息": "缺少用户 UID，请填写 '用户 UID'", "调试": {"原始输入": raw_user_id}}
                return Data(data=result)
            elif not self._is_valid_user_id(user_id):
                result["错误"] = {"类型": "param_error", "消息": "用户 UID 格式不合法，请填写 24 位小红书 UID，例如 636519f2000000001f019e57", "调试": {"原始输入": raw_user_id, "清洗后": user_id, "长度": len(user_id or "")}}
                return Data(data=result)

            # 可选：拉取一次用户信息，便于输出作者维度统计与调试
            user_info = self._get_user_info(user_id)
            if user_info.get("code") != 0:
                result.setdefault("错误列表", []).append(
                    {"步骤": "获取用户信息", "错误": user_info.get("error") or {"类型": "unknown", "消息": user_info.get("message", "未知错误")}}
                )

            total_notes_cnt = 0

            for page_idx in range(max_pages):
                resp = self._get_user_notes(user_id, last_cursor)

                if resp.get("code") != 0:
                    result.setdefault("错误列表", []).append(
                        {"步骤": f"用户笔记 第{page_idx+1}页", "错误": resp.get("error") or {"类型": "unknown", "消息": resp.get("message", "未知错误")}}
                    )

                # 构建页面块并按需过滤用户信息与原始响应
                block: Dict[str, Any] = {
                    "页码": page_idx + 1,
                    "用户ID": user_id,
                    # 顶层用户信息过滤：在原有基础上进一步移除非核心字段
                    "用户信息": self._filter_keys_recursive(
                        user_info,
                        self.USER_INFO_FILTER_KEYS.union(self.USER_INFO_FILTER_KEYS_FOR_USER_NOTES),
                    ),
                    # 原始响应过滤（每页用户笔记列表）：移除 UI/内部用途字段与不必要的子键
                    "原始": self._filter_keys_recursive(
                        resp,
                        self.SEARCH_FILTER_KEYS.union(self.USER_NOTES_ITEM_FILTER_KEYS),
                        self.USER_NOTES_ITEM_CHILD_FILTER_MAP,
                    ),
                    "笔记": [],
                    "请求信息": {
                        "环境": getattr(self, "environment", "中国区"),
                        "用户": {
                            "path_v4": self.PATHS["user_info_v4"],
                            "url_v4": f"{base_url}{self.PATHS['user_info_v4']}",
                            "params_v4": {**self._build_params(required={"userId": user_id}), "token": self._mask_token(token_val)},
                            "path_v3": self.PATHS["user_info_v3"],
                            "url_v3": f"{base_url}{self.PATHS['user_info_v3']}",
                            "params_v3": {**self._build_params(required={"userId": user_id}), "token": self._mask_token(token_val)},
                        },
                        "用户笔记": {
                            "path_v4": self.PATHS["user_note_list_v4"],
                            "url_v4": f"{base_url}{self.PATHS['user_note_list_v4']}",
                            "params_v4": {
                                **self._build_params(required={"userId": user_id}, optional={"lastCursor": last_cursor}),
                                "token": self._mask_token(token_val),
                            },
                            "path_v2": self.PATHS["user_note_list_v2"],
                            "url_v2": f"{base_url}{self.PATHS['user_note_list_v2']}",
                            "params_v2": {
                                **self._build_params(required={"userId": user_id}, optional={"lastCursor": last_cursor}),
                                "token": self._mask_token(token_val),
                            },
                        },
                    },
                }

                if resp.get("code") == 0 and isinstance(resp.get("data"), dict):
                    d = resp["data"]
                    # 进一步清理 interactions 中的 follows 项（不需要关注列表详细信息）
                    try:
                        interactions = (((block.get("用户信息") or {}).get("data") or {}).get("interactions") or [])
                        if isinstance(interactions, list):
                            cleaned = [
                                it for it in interactions
                                if str(it.get("ppType") or it.get("type") or "").lower() != "follows"
                            ]
                            if "data" in (block.get("用户信息") or {}):
                                block["用户信息"]["data"]["interactions"] = cleaned
                    except Exception:
                        pass
                    items = d.get("notes") or d.get("list") or d.get("items") or []
                    for n in items:
                        note_id = (n.get("noteId") or n.get("id") or "")
                        ts = self._normalize_ts(
                            n.get("timestamp")
                            or n.get("update_time")
                            or n.get("publishTime")
                            or n.get("time")
                            or n.get("create_time")
                        )
                        cover_val = self._extract_cover(n)
                        video_master = self._extract_video_master(n)
                        # 过滤作者对象
                        user = self._filter_user_basic(n.get("user") or {})

                        obj: Dict[str, Any] = {
                            "笔记ID": note_id,
                            "笔记链接": self._note_url(note_id) if note_id else "",
                            "摘要": {
                                "用户昵称": user.get("nickname"),
                                "标题": n.get("display_title") or n.get("title"),
                                "正文": None,
                                "点赞数": n.get("likes") or n.get("liked_count"),
                                "评论数": n.get("comments_count"),
                                "收藏数": n.get("collected_count"),
                                "好看数": n.get("nice_count"),
                                "分享数": n.get("share_count"),
                                "图片链接": cover_val,
                                "浏览数": n.get("view_count"),
                                "发布时间": ts,
                                "是否商品笔记": n.get("is_goods_note"),
                                "类型": n.get("type"),
                            },
                            "作者": user,
                        }

                        if video_master:
                            obj["摘要"]["视频链接"] = video_master

                        list_desc = n.get("desc")
                        # 不再调用笔记详情接口：仅使用列表中的 desc 作为正文；缺失时置为 None
                        if isinstance(list_desc, str) and list_desc.strip():
                            obj["摘要"]["正文"] = list_desc
                            obj["摘要"]["标签"] = self._extract_tags_from_text(list_desc)
                        else:
                            obj["摘要"]["正文"] = None
                            obj["摘要"]["标签"] = []

                        block["笔记"].append(obj)
                    total_notes_cnt += len(block["笔记"])

                    block["还有更多"] = d.get("has_more")
                    block["下一页游标"] = d.get("cursor")
                    # 更新下一页游标：无更多或缺失游标则提前结束
                    last_cursor = d.get("cursor") if d.get("has_more") else None
                else:
                    # API 错误页也放入数据，便于前端查看原始响应
                    block.setdefault("还有更多", False)
                    block.setdefault("下一页游标", None)

                result["数据"].append(block)

                if not (last_cursor and block.get("还有更多")):
                    break

        durations = {}
        for path, arr in self._metrics.get("request_durations", {}).items():
            if not arr:
                continue
            durations[path] = {"次数": len(arr), "最短耗时ms": min(arr), "最长耗时ms": max(arr), "平均耗时ms": int(sum(arr) / len(arr))}
        result["meta"]["请求耗时"] = durations
        result["meta"]["版本选择"] = self._metrics.get("version_choice", [])

        try:
            total_notes = 0
            total_pages = 0
            if mode_internal == "keyword_notes":
                for blk in result["数据"]:
                    total_pages += 1
                    try:
                        raw = blk.get("原始", {})
                        d = raw.get("data", {}) if isinstance(raw, dict) else {}
                        items = d.get("items") or d.get("list") or []
                        total_notes += len(items)
                    except Exception:
                        pass
            elif mode_internal == "user_notes":
                for blk in result["数据"]:
                    total_notes += len(blk.get("笔记", []))
            elif mode_internal == "note_comments":
                for blk in result["数据"]:
                    total_notes += len(blk.get("评论", []))
            # 改为 merge 统计：不覆盖已有键，保持页数、条目数等统计并可在前面补充空标题/空正文等指标
            stat = result.setdefault("meta", {}).setdefault("统计", {})
            stat.setdefault("条目数", total_notes)
            stat.setdefault("页数", total_pages)
        except Exception:
            pass

        # 搜索模式：根据你的裁剪诉求，移除顶层的模式/环境/基础地址，专注结果数据
        if mode_internal == "keyword_notes":
            try:
                for k in ["模式", "环境", "基础地址"]:
                    if k in result:
                        result.pop(k, None)
            except Exception:
                pass

        return Data(data=result)

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        def set_show(name: str, show: bool):
            if name in build_config:
                build_config[name]["show"] = show

        def set_required(name: str, required: bool):
            if name in build_config:
                build_config[name]["required"] = required

        current_mode_label = field_value if field_name == "mode" else build_config.get("mode", {}).get("value", getattr(self, "mode", "按关键词采集笔记"))

        set_show("environment", True)
        set_show("token", True)
        # Token 始终必填
        set_required("token", True)

        for name in [
            "input_value", "note_type", "sort", "start_page", "end_page", "time_range", "include_author_detail",
            "note_input", "comment_mode", "include_sub_comments", "comments_last_cursor",
            "xhs_user_id", "user_notes_pages",
        ]:
            set_show(name, False)
            # 默认都不必填，避免隐藏字段参与必填校验
            set_required(name, False)

        if current_mode_label == "按关键词采集笔记":
            for name in ["input_value", "note_type", "sort", "start_page", "end_page", "time_range", "include_author_detail"]:
                set_show(name, True)
            # 仅在该模式下将搜索词标记为必填
            set_required("input_value", True)
        elif current_mode_label == "按笔记采集评论":
            # 评论请求只用 v2 且不分页：隐藏 comments_last_cursor 输入
            for name in ["note_input", "comment_mode", "include_sub_comments"]:
                set_show(name, True)
            # 仅在该模式下将笔记链接/ID标记为必填
            set_required("note_input", True)
        elif current_mode_label == "按用户信息采集笔记":
            for name in ["xhs_user_id", "user_notes_pages"]:
                set_show(name, True)
            # 仅在该模式下将用户 UID 标记为必填
            set_required("xhs_user_id", True)

        return build_config