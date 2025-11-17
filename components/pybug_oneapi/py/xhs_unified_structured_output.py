"""
小红书统一结构化输出组件

功能：
- 根据输入 JSON 顶部（首个“{”后）判断模式，并分派到对应逻辑：
  1) "模式": "按笔记采集评论" -> 评论结构化（comment）
  2) 若无模式但存在顶层 "数据" -> 搜索结构化（search）
  3) "模式": "按用户信息采集笔记" -> 用户笔记结构化（usernotes）
- 输出完全复用并保持与原三组件一致的字段与行为（Data / DataFrame）。

约束：
- 忽略文件中我方已总结的中文映射字段，仅基于原始结构进行抽取。
- 做好兜底：除非完全没有数据，否则不产生 null；字符串用空字符串，数值用 0，布尔用 False。

输入：
- input_data：上游组件输出的 Data / Message（优先使用）
- input_json：原始响应 JSON（字符串或对象，作为备用通道），支持：
  - /components/pybug/final/comment.filtered.json
  - /components/pybug/final/search.filtered.json
  - /components/pybug/final/user.filtered.json（可能外层包裹 results.text.data.text）

输出：
- structured_output: Data（单条直接返回对象，多条以 {"results": [...]} 返回）
- dataframe_output: DataFrame（一条时为单行，多条时为多行）
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple
from datetime import datetime

from langflow.custom.custom_component.component import Component
from langflow.io import HandleInput, MultilineInput, Output
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame


class XHSUnifiedStructuredOutputComponent(Component):
    display_name = "小红书统一结构化输出"
    description = "根据输入自动识别模式并输出与原组件完全一致的结构化数据。"
    documentation: str = "https://docs.langflow.org/components-processing#structured-output"
    name = "XHSUnifiedStructuredOutput"
    icon = "table"

    inputs = [
        HandleInput(
            name="input_data",
            display_name="上游数据",
            info="接收上游组件输出的 Data 或 Message（若存在则优先使用）。",
            input_types=["Data", "Message"],
            required=False,
        ),
        MultilineInput(
            name="input_json",
            display_name="输入JSON（备用）",
            info="原始响应 JSON（字符串或对象），comment/search/user 三类输入均支持。",
            tool_mode=True,
            required=False,
        ),
    ]

    outputs = [
        Output(
            name="structured_output",
            display_name="Structured Output",
            method="build_structured_output",
        ),
        Output(
            name="dataframe_output",
            display_name="Structured Output",
            method="build_structured_dataframe",
        ),
    ]

    # -----------------------------
    # 公用：安全取值与兜底
    # -----------------------------
    @staticmethod
    def _as_str(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    @staticmethod
    def _as_int(value: Any) -> int:
        try:
            if value is None:
                return 0
            if isinstance(value, (int, float)):
                return int(value)
            return int(str(value))
        except Exception:
            return 0

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        return s in {"true", "1", "yes", "y"}

    @staticmethod
    def _format_ts_to_ymdhms(value: Any) -> str:
        """
        将时间戳格式化为中文的“YYYY年MM月DD日 HH时MM分SS秒”。
        - 支持秒或毫秒级时间戳；当值无效或为0时返回空字符串。
        """
        try:
            ts = XHSUnifiedStructuredOutputComponent._as_int(value)
            if ts <= 0:
                return ""
            # 毫秒级时间戳容错
            if ts > 10**11:
                ts = ts // 1000
            dt = datetime.fromtimestamp(ts)
            return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日 {dt.hour:02d}时{dt.minute:02d}分{dt.second:02d}秒"
        except Exception:
            return ""

    # -----------------------------
    # 公用：提取图片 URL（评论/用户笔记使用）
    # -----------------------------
    @staticmethod
    def _extract_image_urls(images_val: Any) -> List[str]:
        urls: List[str] = []
        if images_val is None:
            return urls
        if isinstance(images_val, str):
            parts = [p.strip() for p in re.split(r"[;,\s]+", images_val) if p.strip()]
            urls.extend(parts)
        elif isinstance(images_val, list):
            for item in images_val:
                if isinstance(item, str):
                    if item.strip():
                        urls.append(item.strip())
                elif isinstance(item, dict):
                    for key in ("url", "image_url", "src", "url_size_large"):
                        v = item.get(key)
                        if isinstance(v, str) and v.strip():
                            urls.append(v.strip())
        elif isinstance(images_val, dict):
            for key in ("url", "image_url", "src", "url_size_large"):
                v = images_val.get(key)
                if isinstance(v, str) and v.strip():
                    urls.append(v.strip())
        return urls

    @staticmethod
    def _escape_ctrl_in_strings(s: str) -> str:
        res: List[str] = []
        in_str = False
        esc = False
        for ch in s:
            if in_str:
                if esc:
                    res.append(ch)
                    esc = False
                else:
                    if ch == "\\":
                        res.append(ch)
                        esc = True
                    elif ch == '"':
                        res.append(ch)
                        in_str = False
                    else:
                        oc = ord(ch)
                        if ch == "\n":
                            res.append("\\n")
                        elif ch == "\r":
                            res.append("\\r")
                        elif ch == "\t":
                            res.append("\\t")
                        elif oc < 32:
                            res.append(" ")
                        else:
                            res.append(ch)
            else:
                if ch == '"':
                    res.append(ch)
                    in_str = True
                else:
                    res.append(ch)
        return "".join(res)

    @staticmethod
    def _safe_json_loads_from_string(obj_str: str) -> Any:
        s = obj_str.strip()
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", s, re.DOTALL)
        if m:
            s = m.group(1)
        first = s.find("{")
        last = s.rfind("}")
        candidate = s[first:last + 1] if first != -1 and last != -1 and last > first else s
        candidate = candidate.lstrip("\ufeff")
        candidate2 = XHSUnifiedStructuredOutputComponent._escape_ctrl_in_strings(candidate)
        try:
            return json.loads(candidate2)
        except json.JSONDecodeError:
            fixed = re.sub(r",\s*([}\]])", r"\1", candidate2)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                cnt_double = fixed.count('"')
                cnt_single = fixed.count("'")
                if cnt_single > cnt_double * 2:
                    c2 = fixed.replace("'", '"')
                    c2 = re.sub(r"\bTrue\b", "true", c2)
                    c2 = re.sub(r"\bFalse\b", "false", c2)
                    c2 = re.sub(r"\bNone\b", "null", c2)
                    try:
                        return json.loads(c2)
                    except Exception:
                        pass
                # 容错：解析失败时返回空对象，避免抛错
                return {}

    # -----------------------------
    # 公用：从输入解析为 Python 对象，并返回(doc, 模式字符串或空)
    # 备注：若输入为字符串，严格从首个“{”开始解析。
    #       若输入为 dict，优先解析 results.text.data.text 内嵌 JSON（user.filtered.json 包装场景）。
    # -----------------------------
    def _parse_doc_and_detect_mode(self) -> Tuple[Dict[str, Any] | List[Any], str]:
        # 优先使用上游句柄数据，其次使用备用字符串输入
        obj: Any = None
        payload = getattr(self, "input_data", None)
        if payload is not None:
            base = payload[0] if isinstance(payload, list) and payload else payload
            if base is not None:
                if hasattr(base, "data"):
                    obj = getattr(base, "data")
                elif hasattr(base, "text"):
                    obj = getattr(base, "text")
                else:
                    obj = base
        if obj is None:
            obj = self.input_json

        # 1) 字符串：容错解析
        if isinstance(obj, str):
            try:
                doc = XHSUnifiedStructuredOutputComponent._safe_json_loads_from_string(obj)
            except Exception:
                # 容错：字符串无法解析为 JSON 时，使用空对象继续流程
                doc = {}

        # 2) 字典/列表：直接使用，且尝试解包 user.text 包装
        elif isinstance(obj, (dict, list)):
            doc = obj
            if isinstance(doc, dict):
                inner_text = (((doc.get("results") or {}).get("text") or {}).get("data") or {})
                if isinstance(inner_text, dict) and isinstance(inner_text.get("text"), str):
                    try:
                        doc = XHSUnifiedStructuredOutputComponent._safe_json_loads_from_string(inner_text["text"])  # 解析内嵌字符串 JSON
                    except Exception:
                        pass
        else:
            # 容错：未知类型时返回空对象，避免抛错
            doc = {}

        # 顶部模式判断：仅看顶层（首个“{”后）
        mode_val = ""
        top = doc if isinstance(doc, dict) else {}
        if isinstance(top, dict):
            mode_val = self._as_str(top.get("模式"))

        # 返回(doc, 模式字符串)
        return doc, mode_val

    # -----------------------------
    # 评论模式：与 XHSCommentStructuredOutputComponent 逻辑保持一致
    # -----------------------------
    def _augment_comment_content(self, base_content: str, comment: Dict[str, Any], reply_target_name: str | None) -> str:
        content = base_content or ""
        if reply_target_name:
            content = f"回复{reply_target_name}：" + content
        image_urls = []
        for key in ("images", "image_urls", "imgs"):
            if key in comment:
                image_urls = self._extract_image_urls(comment.get(key))
                break
        if image_urls:
            content = content + " [图片:" + ";".join(image_urls) + "]"
        return content

    def _map_comment(self, comment: Dict[str, Any], level: str, author_id: str, default_location: str) -> Dict[str, Any]:
        user = comment.get("user") or {}
        nickname = self._as_str(user.get("nickname"))
        red_id = self._as_str(user.get("red_id"))
        official_verified = self._as_bool(user.get("official_verified"))
        official_verified_str = "是" if official_verified else "否"

        return {
            "昵称": nickname,
            "评论内容": self._as_str(comment.get("content")),
            "点赞数": self._as_int(comment.get("like_count")),
            "发布时间": self._as_int(comment.get("time")),
            "发布地点": (self._as_str(comment.get("ip_location")) or self._as_str(default_location)),
            "评论级别": level,
            "用户昵称": nickname,
            "小红书号": red_id,
            "作者ID": self._as_str(author_id),
            "是否官方认证": official_verified_str,
        }

    def _build_comment_base(self, doc: Dict[str, Any] | List[Any]) -> List[Dict[str, Any]]:
        # 兼容原文件的解析与遍历逻辑
        datasets: List[Dict[str, Any]] = []
        if isinstance(doc, dict):
            data_list = doc.get("数据")
            if isinstance(data_list, list):
                datasets = [d for d in data_list if isinstance(d, dict)]
            else:
                datasets = [doc]
        elif isinstance(doc, list):
            datasets = [d for d in doc if isinstance(d, dict)]

        final_results: List[Dict[str, Any]] = []

        global_default_location = ""
        if isinstance(doc, dict):
            global_default_location = self._as_str(doc.get("环境")) or "未知"

        for ds in datasets:
            author_id = ""
            raw_list = ds.get("原始")
            root_seq: List[Dict[str, Any]] = []
            root_nickname_by_id: Dict[str, str] = {}

            if isinstance(raw_list, list):
                for raw in raw_list:
                    if not isinstance(raw, dict):
                        continue
                    if raw.get("code") != 0:
                        continue
                    data_node = raw.get("data") or {}
                    if not isinstance(data_node, dict):
                        continue
                    author_id = self._as_str(data_node.get("user_id")) or author_id
                    comments = data_node.get("comments") or []
                    if isinstance(comments, list):
                        for c in comments:
                            if isinstance(c, dict):
                                mapped = self._map_comment(c, level="根评论", author_id=author_id, default_location=global_default_location)
                                mapped["评论内容"] = self._augment_comment_content(mapped["评论内容"], c, reply_target_name=None)
                                cid = self._as_str(c.get("id"))
                                root_seq.append({"id": cid, "mapped": mapped, "src": c})
                                root_nickname_by_id[cid] = self._as_str((c.get("user") or {}).get("nickname"))

            replies_groups = ds.get("评论")
            replies_by_root: Dict[str, List[Dict[str, Any]]] = {}
            orphan_replies: List[Dict[str, Any]] = []
            if isinstance(replies_groups, list):
                for rg in replies_groups:
                    if not isinstance(rg, dict):
                        continue
                    root_id_cn = rg.get("评论ID")
                    root_id_key = self._as_str(root_id_cn) if root_id_cn is not None else ""
                    raw_replies = rg.get("二级评论原始响应")
                    if not isinstance(raw_replies, list):
                        continue
                    for rr in raw_replies:
                        if not isinstance(rr, dict):
                            continue
                        if rr.get("code") != 0:
                            continue
                        data_node = rr.get("data") or {}
                        comments = data_node.get("comments") or []
                        if isinstance(comments, list):
                            for c in comments:
                                if isinstance(c, dict):
                                    mapped = self._map_comment(c, level="二级评论", author_id=author_id, default_location=global_default_location)
                                    entry = {"mapped": mapped, "src": c, "root_id": root_id_key}
                                    if root_id_key:
                                        replies_by_root.setdefault(root_id_key, []).append(entry)
                                    else:
                                        orphan_replies.append(entry)

            for root in root_seq:
                final_results.append(root["mapped"])
                rid = root["id"]
                root_nick = root_nickname_by_id.get(rid, "")
                for rp in replies_by_root.get(rid, []):
                    rp_m = rp["mapped"]
                    rp_m["评论内容"] = self._augment_comment_content(rp_m["评论内容"], rp["src"], reply_target_name=root_nick)
                    final_results.append(rp_m)

            if orphan_replies:
                last_root_nick = root_nickname_by_id.get(root_seq[-1]["id"], "") if root_seq else ""
                for rp in orphan_replies:
                    rp_m = rp["mapped"]
                    rp_m["评论内容"] = self._augment_comment_content(rp_m["评论内容"], rp["src"], reply_target_name=last_root_nick or None)
                    final_results.append(rp_m)

        return final_results

    # -----------------------------
    # 搜索模式：与 XHSSearchStructuredOutputComponent 逻辑保持一致
    # -----------------------------
    def _extract_cover_url(self, note: Dict[str, Any]) -> str:
        images_val = note.get("images_list")
        urls: List[str] = []
        if isinstance(images_val, list):
            for item in images_val:
                if isinstance(item, dict):
                    v = item.get("url") or item.get("url_size_large") or item.get("image_url") or item.get("src")
                    if isinstance(v, str) and v.strip():
                        urls.append(v.strip())
                elif isinstance(item, str) and item.strip():
                    urls.append(item.strip())
        elif isinstance(images_val, dict):
            for key in ("url", "url_size_large", "image_url", "src"):
                v = images_val.get(key)
                if isinstance(v, str) and v.strip():
                    urls.append(v.strip())
        return urls[0] if urls else ""

    def _extract_video_url(self, note: Dict[str, Any]) -> str:
        vi = note.get("video_info_v2") or {}
        media = (vi.get("media") or {})
        stream = (media.get("stream") or {})
        for key in ("h264", "h265"):
            arr = stream.get(key)
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, dict):
                        url = item.get("master_url")
                        if isinstance(url, str) and url.strip():
                            return url.strip()
                        backups = item.get("backup_urls")
                        if isinstance(backups, list):
                            for b in backups:
                                if isinstance(b, str) and b.strip():
                                    return b.strip()
        return ""

    def _extract_tags(self, note: Dict[str, Any]) -> str:
        tags: List[str] = []
        for key in ("tag_list", "note_tag_list", "tags"):
            val = note.get(key)
            if isinstance(val, list):
                for t in val:
                    if isinstance(t, str) and t.strip():
                        tags.append(t.strip())
                    elif isinstance(t, dict):
                        name = t.get("name") or t.get("title")
                        if isinstance(name, str) and name.strip():
                            tags.append(name.strip())
        if not tags:
            desc = self._as_str(note.get("desc"))
            if desc:
                tags += [m.strip() for m in re.findall(r"#([^#\n\r]+)", desc) if m.strip()]
        dedup: List[str] = []
        for t in tags:
            if t not in dedup:
                dedup.append(t)
        return ";".join(dedup) if dedup else ""

    def _map_search_note(self, note: Dict[str, Any], include_author_details: bool) -> Dict[str, Any]:
        user = note.get("user") or {}
        nickname = self._as_str(user.get("nickname"))
        red_id = self._as_str(user.get("red_id"))
        official_verified = self._as_bool(user.get("official_verified"))
        official_verified_str = "是" if official_verified else "否"

        title = self._as_str(note.get("title")) or self._as_str(note.get("display_title"))
        desc = self._as_str(note.get("desc"))

        like_count = self._as_int(note.get("liked_count")) or self._as_int(note.get("likes"))
        comment_count = self._as_int(note.get("comments_count"))
        collect_count = self._as_int(note.get("collected_count"))
        nice_count = self._as_int(note.get("nice_count"))
        share_count = self._as_int(note.get("shared_count")) or self._as_int(note.get("share_count"))
        note_type = self._as_str(note.get("type"))
        # 类型显示规则：normal → 图文笔记；video → 视频笔记；其他保持原值
        if note_type == "normal":
            display_type = "图文笔记"
        elif note_type == "video":
            display_type = "视频笔记"
        else:
            display_type = note_type
        note_id = self._as_str(note.get("id"))

        link = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""
        tags = self._extract_tags(note)
        cover_url = self._extract_cover_url(note)
        video_url = self._extract_video_url(note)
        publish_time = self._as_int(note.get("timestamp")) or self._as_int(note.get("create_time"))
        publish_time_str = self._format_ts_to_ymdhms(publish_time)

        mapped: Dict[str, Any] = {
            "标题": title,
            "点赞数": like_count,
            "评论数": comment_count,
            "收藏数": collect_count,
            "好看数": nice_count,
            "分享数": share_count,
            "笔记类型": display_type,
            "笔记id": note_id,
            "笔记链接": link,
            "笔记正文": desc,
            "笔记tag": tags,
            "封面图链接": cover_url,
            "视频链接": video_url,
            "发布时间": publish_time_str,
            "作者昵称": nickname,
            "小红书号": red_id,
            "是否官方认证": official_verified_str,
        }

        if include_author_details:
            user_id = self._as_str(user.get("userid"))
            author_home = f"https://www.xiaohongshu.com/user/profile/{user_id}" if user_id else ""
            mapped.update({
                "作者粉丝数": 0,
                "作者获赞与收藏数": 0,
                "作者简介": "",
                "作者主页链接": author_home,
            })

            author_fields = [
                mapped.get("作者粉丝数"),
                mapped.get("作者获赞与收藏数"),
                mapped.get("作者简介"),
                mapped.get("作者主页链接"),
            ]
            all_empty = (
                (self._as_int(author_fields[0]) == 0)
                and (self._as_int(author_fields[1]) == 0)
                and (self._as_str(author_fields[2]) == "")
                and (self._as_str(author_fields[3]) == "")
            )
            if all_empty:
                for k in ("作者粉丝数", "作者获赞与收藏数", "作者简介", "作者主页链接"):
                    mapped.pop(k, None)

        return mapped

    def _build_search_base(self, doc: Dict[str, Any] | List[Any]) -> List[Dict[str, Any]]:
        datasets: List[Dict[str, Any]] = []
        if isinstance(doc, dict):
            data_list = doc.get("数据")
            if isinstance(data_list, list):
                datasets = [d for d in data_list if isinstance(d, dict)]
            else:
                datasets = [doc]
        elif isinstance(doc, list):
            datasets = [d for d in doc if isinstance(d, dict)]

        final_results: List[Dict[str, Any]] = []
        for ds in datasets:
            raw = ds.get("原始")
            raw_candidates: List[Dict[str, Any]] = []
            if isinstance(raw, dict):
                raw_candidates = [raw]
            elif isinstance(raw, list):
                raw_candidates = [r for r in raw if isinstance(r, dict)]

            for r in raw_candidates:
                if r.get("code") != 0:
                    continue
                data_node = r.get("data") or {}
                items = data_node.get("items") or []
                if not isinstance(items, list):
                    continue
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    note = it.get("note")
                    if isinstance(note, dict):
                        mapped = self._map_search_note(note, include_author_details=False)
                        final_results.append(mapped)
        return final_results

    # -----------------------------
    # 用户笔记模式：与 XHSUserNotesStructuredOutputComponent 逻辑保持一致
    # -----------------------------
    def _map_user_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        user = note.get("user") or {}
        nickname = self._as_str(user.get("nickname"))
        note_id = self._as_str(note.get("id"))

        title = self._as_str(note.get("title")) or self._as_str(note.get("display_title"))
        desc = self._as_str(note.get("desc"))

        like_count = self._as_int(note.get("liked_count")) or self._as_int(note.get("likes"))
        comment_count = self._as_int(note.get("comments_count"))
        collect_count = self._as_int(note.get("collected_count"))
        note_type = self._as_str(note.get("type"))
        nice_count = self._as_int(note.get("nice_count")) if note_type == "video" else 0
        share_count = self._as_int(note.get("shared_count")) or self._as_int(note.get("share_count"))
        view_count = self._as_int(note.get("view_count"))

        images = self._extract_image_urls(note.get("images_list"))
        images_str = ";".join(images) if images else ""

        publish_time = self._as_int(note.get("create_time")) or self._as_int(note.get("timestamp"))

        # 类型显示规则：normal → 图文笔记；video → 视频笔记；其他保持原值
        if note_type == "normal":
            display_type = "图文笔记"
        elif note_type == "video":
            display_type = "视频笔记"
        else:
            display_type = note_type

        # 链接规则：按用户信息采集笔记，链接应为 explore/<note_id>
        link = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""

        return {
            "用户昵称": nickname,
            "笔记ID": note_id,
            "笔记链接": link,
            "笔记标题": title,
            "笔记正文": desc,
            "点赞数": like_count,
            "评论数": comment_count,
            "收藏数": collect_count,
            "好看数": nice_count,
            "分享次数": share_count,
            "笔记图片链接": images_str,
            "浏览数": view_count,
            "发布时间": publish_time,
            "是否是商品笔记": self._as_bool(note.get("is_goods_note")),
            "笔记类型": display_type,
        }

    def _build_user_notes_base(self, doc: Dict[str, Any] | List[Any]) -> List[Dict[str, Any]]:
        datasets: List[Dict[str, Any]] = []
        if isinstance(doc, dict):
            data_list = doc.get("数据")
            if isinstance(data_list, list):
                datasets = [d for d in data_list if isinstance(d, dict)]
            else:
                datasets = [doc]
        elif isinstance(doc, list):
            datasets = [d for d in doc if isinstance(d, dict)]

        final_results: List[Dict[str, Any]] = []
        for ds in datasets:
            raw = ds.get("原始")
            raw_candidates: List[Dict[str, Any]] = []
            if isinstance(raw, dict):
                raw_candidates = [raw]
            elif isinstance(raw, list):
                raw_candidates = [r for r in raw if isinstance(r, dict)]

            for r in raw_candidates:
                if r.get("code") != 0:
                    continue
                data_node = r.get("data") or {}
                notes = data_node.get("notes") or []
                if not isinstance(notes, list):
                    continue
                for n in notes:
                    if isinstance(n, dict):
                        mapped = self._map_user_note(n)
                        final_results.append(mapped)
        return final_results

    # -----------------------------
    # 统一输出
    # -----------------------------
    def build_structured_output(self) -> Data:
        doc, mode_val = self._parse_doc_and_detect_mode()

        # 判定顺序调整：优先使用明确的模式字符串，避免“顶层有数据”误判
        if mode_val == "按笔记采集评论":
            output = self._build_comment_base(doc)
        elif mode_val == "按用户信息采集笔记":
            output = self._build_user_notes_base(doc)
        elif isinstance(doc, dict) and isinstance(doc.get("数据"), list):
            # 顶层存在“数据”但无模式字符串时，根据原始 data 的结构区分 search / usernotes / comment
            chosen = "search"
            data_list = doc.get("数据") or []
            first_ds = None
            if isinstance(data_list, list):
                for d in data_list:
                    if isinstance(d, dict):
                        first_ds = d
                        break
            if isinstance(first_ds, dict):
                raw = first_ds.get("原始")
                raw_candidates: List[Dict[str, Any]] = []
                if isinstance(raw, dict):
                    raw_candidates = [raw]
                elif isinstance(raw, list):
                    raw_candidates = [r for r in raw if isinstance(r, dict)]
                for r in raw_candidates:
                    if r.get("code") != 0:
                        continue
                    dn = r.get("data") or {}
                    if isinstance(dn, dict):
                        if isinstance(dn.get("notes"), list):
                            chosen = "usernotes"
                            break
                        elif isinstance(dn.get("items"), list):
                            chosen = "search"
                            break
                        elif isinstance(dn.get("comments"), list):
                            chosen = "comment"
                            break
            if chosen == "usernotes":
                output = self._build_user_notes_base(doc)
            elif chosen == "comment":
                output = self._build_comment_base(doc)
            else:
                output = self._build_search_base(doc)
        else:
            # 兜底：按搜索模式处理
            output = self._build_search_base(doc)

        if not isinstance(output, list) or not output:
            # 容错：无结构化结果时返回空结果，避免抛错
            return Data(data={"results": []})
        if len(output) == 1:
            return Data(data=output[0])
        return Data(data={"results": output})

    def build_structured_dataframe(self) -> DataFrame:
        doc, mode_val = self._parse_doc_and_detect_mode()

        if mode_val == "按笔记采集评论":
            output = self._build_comment_base(doc)
        elif mode_val == "按用户信息采集笔记":
            output = self._build_user_notes_base(doc)
        elif isinstance(doc, dict) and isinstance(doc.get("数据"), list):
            chosen = "search"
            data_list = doc.get("数据") or []
            first_ds = None
            if isinstance(data_list, list):
                for d in data_list:
                    if isinstance(d, dict):
                        first_ds = d
                        break
            if isinstance(first_ds, dict):
                raw = first_ds.get("原始")
                raw_candidates: List[Dict[str, Any]] = []
                if isinstance(raw, dict):
                    raw_candidates = [raw]
                elif isinstance(raw, list):
                    raw_candidates = [r for r in raw if isinstance(r, dict)]
                for r in raw_candidates:
                    if r.get("code") != 0:
                        continue
                    dn = r.get("data") or {}
                    if isinstance(dn, dict):
                        if isinstance(dn.get("notes"), list):
                            chosen = "usernotes"
                            break
                        elif isinstance(dn.get("items"), list):
                            chosen = "search"
                            break
                        elif isinstance(dn.get("comments"), list):
                            chosen = "comment"
                            break
            if chosen == "usernotes":
                output = self._build_user_notes_base(doc)
            elif chosen == "comment":
                output = self._build_comment_base(doc)
            else:
                output = self._build_search_base(doc)
        else:
            output = self._build_search_base(doc)

        if not isinstance(output, list) or not output:
            # 容错：无结构化结果时返回空 DataFrame
            return DataFrame([])
        if len(output) == 1:
            return DataFrame([output[0]])
        return DataFrame(output)