import json
import os
from typing import Any, Dict, Tuple


class XHSFilter:
    """
    复刻 XHSFilterComponent 的核心过滤逻辑，用于离线批量处理 JSON 文件。
    仅保留与业务相关的字段，统一移除明确的技术噪声，并在顶层增加统计信息。
    """

    # === 通用过滤策略 ===
    def should_keep_key(self, key: str) -> bool:
        if not isinstance(key, str):
            return False

        keep_exact = {
            # 顶部与结构
            "模式", "环境", "基础地址", "数据", "data", "原始", "meta", "请求耗时", "版本选择", "统计",
            "页码", "还有更多", "下一页游标", "result", "items", "ads", "note", "notes", "comments",
            "请求信息", "code", "message", "message_cn", "recordTime",
            # 用户信息
            "用户", "用户信息", "user", "userid", "user_id", "nickname", "red_id",
            "official_verified", "red_official_verified",
            # 用户模式补充保留字段
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

        keep_substrings = [
            "url", "image", "video", "note", "user", "count", "time", "desc", "title",
            # 中文模糊保留
            "内容", "地点", "昵称", "评论", "认证", "ID",
        ]

        if key in keep_exact:
            return True
        for sub in keep_substrings:
            if sub in key:
                return True
        return False

    def is_noise_key(self, key: str) -> bool:
        if not isinstance(key, str):
            return False
        noise_exact = {
            "ssim", "psnr", "vmaf", "rotate", "quality_type", "stream_desc",
            "weight", "size", "volume", "audio_bitrate", "audio_channels", "video_bitrate",
            "default_stream",
        }
        return key in noise_exact

    def recursive_filter_with_rules(self, obj: Any) -> Any:
        if isinstance(obj, list):
            return [self.recursive_filter_with_rules(item) for item in obj]
        elif isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                if self.is_noise_key(k):
                    continue
                if self.should_keep_key(k):
                    new_dict[k] = self.recursive_filter_with_rules(v)
            return new_dict
        else:
            return obj

    def filter_search_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        filtered = self.recursive_filter_with_rules(data)
        if isinstance(data, dict):
            if "模式" in data:
                filtered["模式"] = data.get("模式")
            if "meta" in data:
                filtered["meta"] = self.recursive_filter_with_rules(data.get("meta"))
        return filtered

    def filter_comment_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        filtered = self.recursive_filter_with_rules(data)
        if isinstance(data, dict):
            if "模式" in data:
                filtered["模式"] = data.get("模式")
            if "meta" in data:
                filtered["meta"] = self.recursive_filter_with_rules(data.get("meta"))
        return filtered

    def filter_user_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        filtered = self.recursive_filter_with_rules(data)
        if isinstance(data, dict):
            if "模式" in data:
                filtered["模式"] = data.get("模式")
            if "meta" in data:
                filtered["meta"] = self.recursive_filter_with_rules(data.get("meta"))
        # 顶层聚合 notes_flat
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

    def _count_key_lists(self, obj: Any, keys=("items", "notes", "comments", "notes_flat")) -> Dict[str, int]:
        counts = {k: 0 for k in keys}
        def _walk(o: Any):
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

    def apply(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        mode = None
        if isinstance(data, dict):
            mode = data.get("模式")
            if not mode and "数据" in data:
                mode = "按关键词采集笔记"
            if not mode:
                data_list = data.get("result")
                if isinstance(data_list, list) and data_list:
                    first = data_list[0]
                    if isinstance(first, dict):
                        mode = first.get("模式")

        filtered_data: Dict[str, Any] = {}
        if mode and ("按关键词采集笔记" in mode):
            filtered_data = self.filter_search_data(data)
        elif mode and ("按笔记采集评论" in mode):
            filtered_data = self.filter_comment_data(data)
        elif mode and (("按用户采集笔记" in mode) or ("按用户信息采集笔记" in mode)):
            filtered_data = self.filter_user_data(data)
        else:
            # 未识别模式，原样返回
            filtered_data = data
            mode = mode or "未识别"

        if isinstance(data, dict) and "模式" in data and isinstance(filtered_data, dict):
            filtered_data.setdefault("模式", data.get("模式"))

        # 增加过滤后统计
        if isinstance(filtered_data, dict):
            c = self._count_key_lists(filtered_data)
            filtered_data["过滤后统计"] = {
                "items条数": c.get("items", 0),
                "notes条数": c.get("notes", 0),
                "comments条数": c.get("comments", 0),
                "notes_flat条数": c.get("notes_flat", 0),
            }

        return filtered_data, mode


def main():
    # 在仓库根目录执行脚本时，final 目录位于 components/pybug/final
    base_dir = os.path.join(os.getcwd(), "components/pybug/final")
    input_files = [
        os.path.join(base_dir, "comment.json"),
        os.path.join(base_dir, "search.json"),
        os.path.join(base_dir, "user.json"),
    ]

    filt = XHSFilter()
    for in_path in input_files:
        name = os.path.basename(in_path)
        out_path = os.path.join(base_dir, name.replace(".json", ".filtered.json"))
        try:
            with open(in_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ERROR] 无法读取 {name}: {e}")
            continue

        try:
            filtered, mode = filt.apply(data)
        except Exception as e:
            print(f"[ERROR] 处理 {name} 时出错: {e}")
            continue

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(filtered, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 无法写入 {out_path}: {e}")
            continue

        stats = filtered.get("过滤后统计", {}) if isinstance(filtered, dict) else {}
        print(
            f"[OK] {name} -> {os.path.basename(out_path)} | 模式: {mode} | "
            f"items={stats.get('items条数', 0)}, notes={stats.get('notes条数', 0)}, "
            f"comments={stats.get('comments条数', 0)}, notes_flat={stats.get('notes_flat条数', 0)}"
        )


if __name__ == "__main__":
    main()