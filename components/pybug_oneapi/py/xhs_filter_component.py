import json
# 使用 Langflow 的标准组件基类（带有 build_results 等内部方法）
from langflow.custom.custom_component.component import Component
# 统一使用 lfx.io 提供的输入/输出类型，避免跨模块类型不一致
from langflow.inputs.inputs import MessageInput
from langflow.template import Output
from langflow.schema.message import Message


class XHSFilterComponent(Component):
    display_name: str = "小红书数据过滤器"
    description: str = "根据模式（关键词、评论、用户）过滤小红书 API 返回的 JSON，尽量保留有用信息，仅移除明确无用的技术噪声。支持多图片/多视频 URL 全量保留。"
    icon = "filter"
    name = "XHSFilter"

    inputs = [
        MessageInput(
            name="input_message",
            display_name="输入消息",
            info="包含 JSON 数据的消息对象。",
        ),
    ]

    outputs = [
        Output(display_name="过滤后的消息", name="filtered_message", method="filter_message"),
    ]

    # === 通用过滤策略 ===
    def should_keep_key(self, key: str) -> bool:
        """
        判断某个键是否应被保留（模式通用规则）。
        设计原则：
        - 保留所有明显与业务相关的键（id、用户、笔记、媒体、统计、计数、时间、URL 等）
        - 仅过滤确定无用的调试/技术指标键（如 ssim/psnr/vmaf/rotate/quality_type 等）
        """
        if not isinstance(key, str):
            return False

        # 明确保留：结构/业务核心字段
        keep_exact = {
            # 顶部与结构
            "模式", "环境", "基础地址", "数据", "data", "原始", "meta", "请求耗时", "版本选择", "统计",
            "页码", "还有更多", "下一页游标", "result", "items", "ads", "note", "notes", "comments",
            "请求信息", "code", "message", "message_cn", "recordTime",
            # 用户信息
            "用户", "用户信息", "user", "userid", "user_id", "nickname", "red_id",
            "official_verified", "red_official_verified",
            # 用户模式补充保留字段（避免误删）
            "liked", "fans", "collected", "ip_location", "location", "images",
            "user_desc_info", "interactions",
            # 笔记/内容
            "id", "note_id", "title", "display_title", "desc", "content", "type",
            "time_desc", "create_time", "timestamp", "update_time",
            # 计数相关
            "liked_count", "likes", "comments_count", "collected_count", "share_count",
            "nice_count", "view_count", "is_goods_note",
            # 媒体相关
            "url", "urls", "share_link", "images", "image", "images_list",
            "cover", "thumbnail", "first_frame",
            "video_info", "video_info_v2", "media", "stream", "streams",
            "h264", "h265", "master_url", "backup_urls",
            # 评论模式中文字段（明确保留）
            "评论ID", "昵称", "小红书号", "评论内容", "点赞数", "发布时间", "发布地点",
            "二级评论数", "评论级别", "作者ID", "是否官方认证",
        }

        # 模糊保留：包含这些子串的键也保留（尽量覆盖可能的变体）
        keep_substrings = [
            "url", "image", "video", "note", "user", "count", "time", "desc", "title",
            # 兼容中文字段的模糊保留（避免误删有相关性的中文键）
            "内容", "地点", "昵称", "评论", "认证", "ID",
        ]

        if key in keep_exact:
            return True
        for sub in keep_substrings:
            if sub in key:
                return True
        return False

    def is_noise_key(self, key: str) -> bool:
        """
        判断某个键是否为明确无用的技术噪声（跨模式统一过滤）。
        注意：只过滤高度确定无用的指标，避免误删潜在相关字段。
        """
        if not isinstance(key, str):
            return False
        noise_exact = {
            # 视频编码评估/技术指标，在业务侧通常完全用不到
            "ssim", "psnr", "vmaf", "rotate", "quality_type", "stream_desc",
            "weight", "size", "volume", "audio_bitrate", "audio_channels", "video_bitrate",
            "default_stream",
        }
        return key in noise_exact

    def recursive_filter_with_rules(self, obj):
        """根据通用规则递归过滤对象。保留相关性强的字段，仅移除明确噪声。"""
        if isinstance(obj, list):
            return [self.recursive_filter_with_rules(item) for item in obj]
        elif isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                # 优先过滤明确噪声键
                if self.is_noise_key(k):
                    continue
                # 保留相关键，递归处理其值
                if self.should_keep_key(k):
                    new_dict[k] = self.recursive_filter_with_rules(v)
            return new_dict
        else:
            return obj

    def filter_search_data(self, data):
        """过滤“按关键词采集笔记”模式的数据（尽量保留相关信息）。"""
        # 基于通用规则做一次过滤
        filtered = self.recursive_filter_with_rules(data)
        # 兜底：确保顶层保留“模式”和“meta”
        if isinstance(data, dict):
            if "模式" in data:
                filtered["模式"] = data.get("模式")
            if "meta" in data:
                filtered["meta"] = self.recursive_filter_with_rules(data.get("meta"))
        return filtered

    def filter_comment_data(self, data):
        """过滤“按笔记采集评论”模式的数据（尽量保留相关信息）。"""
        filtered = self.recursive_filter_with_rules(data)
        if isinstance(data, dict):
            if "模式" in data:
                filtered["模式"] = data.get("模式")
            if "meta" in data:
                filtered["meta"] = self.recursive_filter_with_rules(data.get("meta"))
        return filtered

    def filter_user_data(self, data):
        """过滤“按用户采集笔记”模式的数据（尽量保留相关信息）。"""
        filtered = self.recursive_filter_with_rules(data)
        if isinstance(data, dict):
            if "模式" in data:
                filtered["模式"] = data.get("模式")
            if "meta" in data:
                filtered["meta"] = self.recursive_filter_with_rules(data.get("meta"))
        # 顶层聚合：将 数据[*].原始.data.notes 聚合为顶层 notes_flat，便于直接查看
        try:
            notes_flat = []
            if isinstance(filtered, dict) and isinstance(filtered.get("数据"), list):
                for item in filtered.get("数据", []):
                    if isinstance(item, dict):
                        raw = item.get("原始")
                        if isinstance(raw, dict):
                            inner_data = raw.get("data")
                            if isinstance(inner_data, dict):
                                notes = inner_data.get("notes")
                                if isinstance(notes, list):
                                    notes_flat.extend(notes)
            if notes_flat:
                filtered["notes_flat"] = notes_flat
        except Exception:
            pass
        return filtered

    def filter_message(self) -> Message:
        input_obj = self.input_message
        original_text_content = ""
        # 优先将输入转换为字符串形式，用于错误回显
        if isinstance(input_obj, Message):
            original_text_content = getattr(input_obj, "text", "")
            if not original_text_content and isinstance(getattr(input_obj, "data", None), (dict, list)):
                try:
                    original_text_content = json.dumps(getattr(input_obj, "data"), ensure_ascii=False, indent=2)
                except:
                    pass
        elif isinstance(input_obj, str):
            original_text_content = input_obj
        elif isinstance(input_obj, (dict, list)):
            try:
                original_text_content = json.dumps(input_obj, ensure_ascii=False, indent=2)
            except:
                pass

        data = None
        input_content = None

        # 1. 从 Message 对象中提取核心内容（字符串或字典）
        if isinstance(self.input_message, Message):
            msg = self.input_message
            text = getattr(msg, "text", None)
            msg_data = getattr(msg, "data", None)
            if isinstance(text, str) and text.strip():
                input_content = text.strip()
            elif isinstance(msg_data, (dict, list)):
                input_content = msg_data
        else:
            input_content = self.input_message

        # 2. 解析核心内容，得到 data 字典
        if isinstance(input_content, dict):
            data = input_content
        elif isinstance(input_content, str):
            s = input_content
            try:
                data = json.loads(s)
            except json.JSONDecodeError:
                # 尝试作为 Langflow 输出结构进行解析
                try:
                    wrapper_dict = json.loads(s)
                    nested_text = wrapper_dict.get("results", {}).get("text", {}).get("text")
                    if isinstance(nested_text, str) and nested_text.strip():
                        data = json.loads(nested_text)
                    else:
                        raise ValueError("未找到嵌套的JSON文本。")
                except Exception:
                    # 如果还是失败，尝试清理 Markdown 格式
                    s2 = s.replace("﻿", "").strip()
                    if s2.startswith("```json"):
                        s2 = s2[len("```json"):].strip()
                    if s2.startswith("```") and s2.endswith("```"):
                        s2 = s2[3:-3].strip()
                    s2 = s2.strip("`").strip()
                    try:
                        data = json.loads(s2)
                    except Exception:
                        self.status = "输入的不是有效 JSON 字符串。"
                        return Message(text=original_text_content)

        if data is None:
            self.status = "输入类型不正确或无法解析，应为 JSON 字符串或字典。"
            return Message(text=original_text_content)

        mode = data.get("模式")

        # 如果没有 “模式” 字段，但有 “数据” 字段，则认为是“按关键词采集笔记”
        if not mode and "数据" in data:
            mode = "按关键词采集笔记"

        # 如果仍然没有模式，则尝试从 result 列表中获取
        if not mode:
            data_list = data.get("result")
            if data_list and isinstance(data_list, list) and data_list:
                if isinstance(data_list[0], dict):
                    mode = data_list[0].get("模式")

        if not mode:
            self.status = "未识别模式，原样输出。"
            return Message(text=json.dumps(data, ensure_ascii=False, indent=2))

        filtered_data = {}
        if "按关键词采集笔记" in mode:
            filtered_data = self.filter_search_data(data)
        elif "按笔记采集评论" in mode:
            filtered_data = self.filter_comment_data(data)
        elif ("按用户采集笔记" in mode) or ("按用户信息采集笔记" in mode):
            filtered_data = self.filter_user_data(data)
        else:
            self.status = f"未识别模式，原样输出。模式值: {mode}"
            return Message(text=json.dumps(data, ensure_ascii=False, indent=2))

        # 保留顶部模式（如果未在过滤后出现，显式添加）
        if isinstance(data, dict) and "模式" in data and isinstance(filtered_data, dict):
            filtered_data.setdefault("模式", data.get("模式"))

        # 增加过滤后统计，帮助确认是否被前端显示长度截断
        def _count_key_lists(obj, keys=("items", "notes", "comments", "notes_flat")):
            counts = {k: 0 for k in keys}
            def _walk(o):
                if isinstance(o, dict):
                    for kk, vv in o.items():
                        if kk in counts and isinstance(vv, list):
                            counts[kk] += len(vv)
                        _walk(vv)
                elif isinstance(o, list):
                    for it in o:
                        _walk(it)
            _walk(obj)
            return counts

        if isinstance(filtered_data, dict):
            c = _count_key_lists(filtered_data)
            filtered_data["过滤后统计"] = {
                "items条数": c.get("items", 0),
                "notes条数": c.get("notes", 0),
                "comments条数": c.get("comments", 0),
                "notes_flat条数": c.get("notes_flat", 0),
            }

        self.status = f"已根据“{mode}”模式完成过滤。"
        return Message(text=json.dumps(filtered_data, ensure_ascii=False, indent=2))