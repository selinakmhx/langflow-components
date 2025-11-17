"""
小红书用户笔记结构化输出组件

功能：
- 从上游传入的 JSON（如 user.filtered.json 的结构）中提取笔记的原始数据，
  输出为结构化结果（Structure Output 类型），包含以下字段：
  - 用户昵称
  - 笔记ID
  - 笔记链接（https://www.xiaohongshu.com/exp）
  - 笔记标题
  - 笔记正文
  - 点赞数
  - 评论数
  - 收藏数
  - 好看数（仅视频笔记）
  - 分享次数
  - 笔记图片链接
  - 浏览数
  - 发布时间
  - 是否是商品笔记
  - 笔记类型

约束：
- 忽略文件中我方已总结的中文映射字段，仅基于原始结构（如 原始.data.notes）进行抽取。
- 做好兜底：除非完全没有数据，否则不产生 null；字符串用空字符串，数值用 0，布尔用 False。

输入：
- input_json: 上游 JSON 字符串（或 Python 字典），支持 /components/pybug/final/user.filtered.json 的结构。

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


class XHSUserNotesStructuredOutputComponent(Component):
    display_name = "小红书用户笔记结构化输出"
    description = "从小红书用户笔记原始 JSON 提取并输出结构化数据，避免依赖中文映射字段。"
    documentation: str = "https://docs.langflow.org/components-processing#structured-output"
    name = "XHSUserNotesStructuredOutput"
    icon = "table"

    inputs = [
        MultilineInput(
            name="input_json",
            display_name="输入JSON",
            info="原始响应 JSON（字符串或对象），例如 user.filtered.json 的内容。",
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
            # 某些包装结构可能把真实 JSON 放在 results.text.data.text
            if isinstance(obj, dict):
                inner_text = (
                    ((obj.get("results") or {}).get("text") or {}).get("data") or {}
                )
                if isinstance(inner_text, dict) and isinstance(inner_text.get("text"), str):
                    try:
                        return json.loads(inner_text["text"])  # 解析内嵌字符串 JSON
                    except Exception:
                        pass
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
    # 公用：提取图片 URL（列表 -> 去空 -> 返回列表）
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

    # -----------------------------
    # 映射：将单条笔记转为目标结构
    # -----------------------------
    def _map_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        user = note.get("user") or {}
        nickname = self._as_str(user.get("nickname"))

        # 文本与标题兜底
        title = self._as_str(note.get("title")) or self._as_str(note.get("display_title"))
        desc = self._as_str(note.get("desc"))

        # 点赞/分享等计数兜底
        like_count = self._as_int(note.get("liked_count")) or self._as_int(note.get("likes"))
        comment_count = self._as_int(note.get("comments_count"))
        collect_count = self._as_int(note.get("collected_count"))
        nice_count = self._as_int(note.get("nice_count")) if self._as_str(note.get("type")) == "video" else 0
        share_count = self._as_int(note.get("shared_count")) or self._as_int(note.get("share_count"))
        view_count = self._as_int(note.get("view_count"))

        # 图片链接（列表 -> 分号连接）
        images = self._extract_image_urls(note.get("images_list"))
        images_str = ";".join(images) if images else ""

        # 发布时间兜底
        publish_time = self._as_int(note.get("create_time")) or self._as_int(note.get("timestamp"))

        return {
            "用户昵称": nickname,
            "笔记ID": self._as_str(note.get("id")),
            "笔记链接": "https://www.xiaohongshu.com/exp",
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
            "笔记类型": self._as_str(note.get("type")),
        }

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

        final_results: List[Dict[str, Any]] = []

        for ds in datasets:
            raw = ds.get("原始")
            # 原始既可能是 dict，也可能是 list（不同采集分页）
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
                        mapped = self._map_note(n)
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