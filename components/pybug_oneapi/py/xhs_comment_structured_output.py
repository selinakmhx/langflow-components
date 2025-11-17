"""
小红书评论结构化输出组件

功能：
- 从上游传入的 JSON（如 comment.filtered.json 格式）中提取评论与二级评论的原始数据，
  输出为结构化结果（Structure Output 类型），包含以下字段：
  - 昵称
  - 评论内容
  - 点赞数
  - 发布时间
  - 发布地点
  - 评论级别（根评论 或 二级评论）
  - 用户昵称
  - 小红书号
  - 作者ID
  - 是否官方认证

约束：
- 忽略文件中我方已总结的中文映射字段（例如“昵称”“小红书号”等已加工字段），
  仅基于原始结构（如 data.comments、二级评论原始响应 data.comments）进行抽取。
- 做好兜底：除非完全没有数据，否则不产生 null；字符串用空字符串，数值用 0，布尔用 False。

输入：
- input_json: 上游 JSON 字符串（或 Python 字典），支持 /components/pybug/final/comment.filtered.json 的结构。

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


class XHSCommentStructuredOutputComponent(Component):
    display_name = "小红书评论结构化输出"
    description = "从小红书评论原始 JSON 提取并输出结构化数据，避免依赖中文映射字段。"
    documentation: str = "https://docs.langflow.org/components-processing#structured-output"
    name = "XHSCommentStructuredOutput"
    icon = "table"

    inputs = [
        MultilineInput(
            name="input_json",
            display_name="输入JSON",
            info="原始响应 JSON（字符串或对象），例如 comment.filtered.json 的内容。",
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
        # 常见布尔字符串兜底
        s = str(value).strip().lower()
        return s in {"true", "1", "yes", "y"}

    # -----------------------------
    # 公用：提取图片 URL 并拼接到内容（以分号分隔）
    # -----------------------------
    @staticmethod
    def _extract_image_urls(images_val: Any) -> List[str]:
        urls: List[str] = []
        if images_val is None:
            return urls
        if isinstance(images_val, str):
            # 简单切分：分号/逗号/空白
            parts = [p.strip() for p in re.split(r"[;,\s]+", images_val) if p.strip()]
            urls.extend(parts)
        elif isinstance(images_val, list):
            for item in images_val:
                if isinstance(item, str):
                    urls.append(item.strip())
                elif isinstance(item, dict):
                    # 常见字段名尝试
                    for key in ("url", "image_url", "src"):
                        v = item.get(key)
                        if isinstance(v, str) and v.strip():
                            urls.append(v.strip())
        elif isinstance(images_val, dict):
            # 单个字典场景
            for key in ("url", "image_url", "src"):
                v = images_val.get(key)
                if isinstance(v, str) and v.strip():
                    urls.append(v.strip())
        return urls

    def _augment_comment_content(self, base_content: str, comment: Dict[str, Any], reply_target_name: str | None) -> str:
        content = base_content or ""
        # 子评论显示“回复某某”
        if reply_target_name:
            # 前缀形式：回复<昵称>：内容
            content = f"回复{reply_target_name}：" + content
        # 追加图片 URL（分号分隔）
        image_urls = []
        # 优先使用评论自身的图片字段
        for key in ("images", "image_urls", "imgs"):
            if key in comment:
                image_urls = self._extract_image_urls(comment.get(key))
                break
        if image_urls:
            content = content + " [图片:" + ";".join(image_urls) + "]"
        return content

    # -----------------------------
    # 映射：将单条评论转为目标结构
    # -----------------------------
    def _map_comment(self, comment: Dict[str, Any], level: str, author_id: str, default_location: str) -> Dict[str, Any]:
        user = comment.get("user") or {}
        nickname = self._as_str(user.get("nickname"))
        red_id = self._as_str(user.get("red_id"))
        official_verified = self._as_bool(user.get("official_verified"))

        return {
            "昵称": nickname,
            "评论内容": self._as_str(comment.get("content")),
            "点赞数": self._as_int(comment.get("like_count")),
            "发布时间": self._as_int(comment.get("time")),
            # 发布地点优先使用原始 ip_location，缺失时兜底为顶层环境（如“中国区”）或“未知”
            "发布地点": (self._as_str(comment.get("ip_location")) or self._as_str(default_location)),
            "评论级别": level,
            "用户昵称": nickname,
            "小红书号": red_id,
            "作者ID": self._as_str(author_id),
            "是否官方认证": official_verified,
        }

    # -----------------------------
    # 核心：构建结构化数据（列表）
    # -----------------------------
    def build_structured_output_base(self) -> List[Dict[str, Any]]:
        doc = self._parse_input()

        # 顶层可能是 dict（含“数据”数组）或直接是列表
        datasets: List[Dict[str, Any]] = []
        if isinstance(doc, dict):
            data_list = doc.get("数据")
            if isinstance(data_list, list):
                datasets = [d for d in data_list if isinstance(d, dict)]
            else:
                # 如果没有“数据”，也可能直接给了一个 data 节点
                datasets = [doc]
        elif isinstance(doc, list):
            datasets = [d for d in doc if isinstance(d, dict)]

        final_results: List[Dict[str, Any]] = []

        # 顶层环境兜底（如“中国区”）
        global_default_location = ""
        if isinstance(doc, dict):
            global_default_location = self._as_str(doc.get("环境")) or "未知"
        
        for ds in datasets:
            # 收集根评论（按出现顺序）和映射
            author_id = ""
            raw_list = ds.get("原始")
            root_seq: List[Dict[str, Any]] = []  # 每项：{"id": str, "mapped": dict, "src": dict}
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
                    # 作者ID（笔记作者）兜底更新
                    author_id = self._as_str(data_node.get("user_id")) or author_id
                    comments = data_node.get("comments") or []
                    if isinstance(comments, list):
                        for c in comments:
                            if isinstance(c, dict):
                                # 构造根评论映射并追加图片信息
                                mapped = self._map_comment(c, level="根评论", author_id=author_id, default_location=global_default_location)
                                mapped["评论内容"] = self._augment_comment_content(mapped["评论内容"], c, reply_target_name=None)
                                cid = self._as_str(c.get("id"))
                                root_seq.append({"id": cid, "mapped": mapped, "src": c})
                                root_nickname_by_id[cid] = self._as_str((c.get("user") or {}).get("nickname"))

            # 收集二级评论并按根评论ID归组
            replies_groups = ds.get("评论")
            replies_by_root: Dict[str, List[Dict[str, Any]]] = {}
            orphan_replies: List[Dict[str, Any]] = []
            if isinstance(replies_groups, list):
                for rg in replies_groups:
                    if not isinstance(rg, dict):
                        continue
                    root_id_cn = rg.get("评论ID")  # 仅用于定位顺序，不参与字段抽取
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
                                    # 回复对象稍后根据根评论昵称补充，同时追加图片信息
                                    entry = {"mapped": mapped, "src": c, "root_id": root_id_key}
                                    if root_id_key:
                                        replies_by_root.setdefault(root_id_key, []).append(entry)
                                    else:
                                        orphan_replies.append(entry)

            # 生成最终序列：根评论 -> 其对应的二级评论（带“回复某某”前缀）
            for root in root_seq:
                final_results.append(root["mapped"])
                rid = root["id"]
                root_nick = root_nickname_by_id.get(rid, "")
                for rp in replies_by_root.get(rid, []):
                    # 为子评论补充“回复某某”并拼接图片URL
                    rp_m = rp["mapped"]
                    rp_m["评论内容"] = self._augment_comment_content(rp_m["评论内容"], rp["src"], reply_target_name=root_nick)
                    final_results.append(rp_m)

            # 将孤立的二级评论（无法定位根）放到最后一个根评论之后，若无根则直接附加
            if orphan_replies:
                if root_seq:
                    # 取最后一个根的昵称用于“回复某某”前缀
                    last_root_nick = root_nickname_by_id.get(root_seq[-1]["id"], "")
                else:
                    last_root_nick = ""
                for rp in orphan_replies:
                    rp_m = rp["mapped"]
                    rp_m["评论内容"] = self._augment_comment_content(rp_m["评论内容"], rp["src"], reply_target_name=last_root_nick or None)
                    final_results.append(rp_m)

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