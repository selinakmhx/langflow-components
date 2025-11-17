"""
小红书搜索结果结构化输出组件



约束：
- 忽略文件中我方已总结的中文映射字段，仅基于原始结构（如 原始.data.items[*].note）进行抽取。
- 做好兜底：除非完全没有数据，否则不产生 null；字符串用空字符串，数值用 0，布尔用 False。

输入：
- input_json: 上游 JSON 字符串（或 Python 字典），支持 /components/pybug/final/search.filtered.json 的结构。

输出：
- structured_output: Data（单条直接返回对象，多条以 {"results": [...]} 返回）
- dataframe_output: DataFrame（一条时为单行，多条时为多行）
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from langflow.custom.custom_component.component import Component
from langflow.io import MultilineInput, Output
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame


class XHSSearchStructuredOutputComponent(Component):
    display_name = "小红书搜索结果结构化输出"
    description = "从小红书搜索原始 JSON 提取并输出结构化数据，避免依赖中文映射字段。"
    documentation: str = "https://docs.langflow.org/components-processing#structured-output"
    name = "XHSSearchStructuredOutput"
    icon = "table"

    inputs = [
        MultilineInput(
            name="input_json",
            display_name="输入JSON",
            info="原始响应 JSON（字符串或对象），例如 search.filtered.json 的内容。",
            tool_mode=True,
            required=True,
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
    # 公用：从输入解析为 Python 对象
    # -----------------------------
    def _parse_input(self) -> Dict[str, Any] | List[Any]:
        obj = self.input_json
        if isinstance(obj, (dict, list)):
            return obj
        if isinstance(obj, str):
            try:
                return json.loads(obj)
            except json.JSONDecodeError:
                msg = "输入不是有效的 JSON 字符串"
                raise ValueError(msg)
        msg = "输入类型不支持：请提供 JSON 字符串或字典/列表"
        raise TypeError(msg)

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

    # -----------------------------
    # 公用：提取图片 URL（封面）
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

    # -----------------------------
    # 公用：提取视频主链路
    # -----------------------------
    def _extract_video_url(self, note: Dict[str, Any]) -> str:
        vi = note.get("video_info_v2") or {}
        media = (vi.get("media") or {})
        stream = (media.get("stream") or {})
        # 优先取 h264 的 master_url，其次 h265
        for key in ("h264", "h265"):
            arr = stream.get(key)
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, dict):
                        url = item.get("master_url")
                        if isinstance(url, str) and url.strip():
                            return url.strip()
                        # 兜底备份链路
                        backups = item.get("backup_urls")
                        if isinstance(backups, list):
                            for b in backups:
                                if isinstance(b, str) and b.strip():
                                    return b.strip()
        return ""

    # -----------------------------
    # 公用：提取笔记标签（优先结构化字段，兜底从正文 #xxx 提取）
    # -----------------------------
    def _extract_tags(self, note: Dict[str, Any]) -> str:
        tags: List[str] = []
        # 常见结构化标签字段
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
        # 兜底：从正文里抓取 #xxx
        if not tags:
            desc = self._as_str(note.get("desc"))
            if desc:
                tags += [m.strip() for m in re.findall(r"#([^#\n\r]+)", desc) if m.strip()]
        # 去重后以分号拼接
        dedup = []
        for t in tags:
            if t not in dedup:
                dedup.append(t)
        return ";".join(dedup) if dedup else ""

    # -----------------------------
    # 映射：将单条笔记转为目标结构（不显示作者详情开关）
    # -----------------------------
    def _map_note(self, note: Dict[str, Any], include_author_details: bool) -> Dict[str, Any]:
        user = note.get("user") or {}
        nickname = self._as_str(user.get("nickname"))
        red_id = self._as_str(user.get("red_id"))
        official_verified = self._as_bool(user.get("official_verified"))

        title = self._as_str(note.get("title")) or self._as_str(note.get("display_title"))
        desc = self._as_str(note.get("desc"))

        like_count = self._as_int(note.get("liked_count")) or self._as_int(note.get("likes"))
        comment_count = self._as_int(note.get("comments_count"))
        collect_count = self._as_int(note.get("collected_count"))
        nice_count = self._as_int(note.get("nice_count"))
        share_count = self._as_int(note.get("shared_count")) or self._as_int(note.get("share_count"))
        note_type = self._as_str(note.get("type"))
        note_id = self._as_str(note.get("id"))

        link = f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""
        tags = self._extract_tags(note)
        cover_url = self._extract_cover_url(note)
        video_url = self._extract_video_url(note)
        publish_time = self._as_int(note.get("timestamp")) or self._as_int(note.get("create_time"))

        mapped: Dict[str, Any] = {
            "标题": title,
            "点赞数": like_count,
            "评论数": comment_count,
            "收藏数": collect_count,
            "好看数": nice_count,
            "分享数": share_count,
            "笔记类型": note_type,
            "笔记id": note_id,
            "笔记链接": link,
            "笔记正文": desc,
            "笔记tag": tags,
            "封面图链接": cover_url,
            "视频链接": video_url,
            "发布时间": publish_time,
            "作者昵称": nickname,
            "小红书号": red_id,
            "是否官方认证": official_verified,
        }

        # 是否包含作者详细信息：默认不选（False）时不显示以下四个字段
        if include_author_details:
            user_id = self._as_str(user.get("userid"))
            author_home = f"https://www.xiaohongshu.com/user/profile/{user_id}" if user_id else ""
            # 无站内详情数据时兜底为空或 0
            mapped.update({
                "作者粉丝数": 0,
                "作者获赞与收藏数": 0,
                "作者简介": "",
                "作者主页链接": author_home,
            })

            # 如果四项都为空（或 0），则不显示它们
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

    # -----------------------------
    # 核心：构建结构化数据（列表）
    # -----------------------------
    def build_structured_output_base(self) -> List[Dict[str, Any]]:
        doc = self._parse_input()

        # 顶层可能是 dict（含“数据”数组）或直接是列表/字典
        datasets: List[Dict[str, Any]] = []
        if isinstance(doc, dict):
            data_list = doc.get("数据")
            if isinstance(data_list, list):
                datasets = [d for d in data_list if isinstance(d, dict)]
            else:
                datasets = [doc]
        elif isinstance(doc, list):
            datasets = [d for d in doc if isinstance(d, dict)]

        # 输出模式不在结果中显示，故不处理

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
                        mapped = self._map_note(note, include_author_details=False)
                        final_results.append(mapped)

        return final_results

    # -----------------------------
    # 输出：Data（Structure Output 类型）
    # -----------------------------
    def build_structured_output(self) -> Data:
        output = self.build_structured_output_base()
        if not isinstance(output, list) or not output:
            msg = "No structured output returned"
            raise ValueError(msg)
        if len(output) == 1:
            return Data(data=output[0])
        return Data(data={"results": output})

    # -----------------------------
    # 输出：DataFrame（便于列表展示）
    # -----------------------------
    def build_structured_dataframe(self) -> DataFrame:
        output = self.build_structured_output_base()
        if not isinstance(output, list) or not output:
            msg = "No structured output returned"
            raise ValueError(msg)
        if len(output) == 1:
            return DataFrame([output[0]])
        return DataFrame(output)