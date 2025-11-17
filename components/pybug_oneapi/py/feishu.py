from langflow.custom import Component
from langflow.io import SecretStrInput, StrInput, DataInput, Output
from langflow.schema import Data
import json
import time
import requests
import re
from typing import Any, Dict, List, Tuple

class FeishuBitableCreateAndWrite(Component):
    display_name = "飞书：解析并写入新表格"
    description = "前台输入 AppID/Secret 与飞书表 URL；解析 Base Token，创建新表并写入记录，失败则回退写入现有表。"
    icon = "table"
    name = "FeishuBitableCreateAndWrite"
    documentation = "https://open.feishu.cn/document/home/index"

    # 将 AppID/Secret 放到最顶端，且为必填
    inputs = [
        SecretStrInput(
            name="app_id",
            display_name="APP_ID（必填）",
            info="飞书应用的 App ID（仅前台输入，不读环境变量）",
            required=True,
        ),
        SecretStrInput(
            name="app_secret",
            display_name="APP_SECRET（必填）",
            info="飞书应用的 App Secret（仅前台输入，不读环境变量）",
            required=True,
        ),
        StrInput(
            name="feishu_url",
            display_name="表格url",
            info="例如 https://www.feishu.cn/base/<app_token>/table/<table_id> 或 https://www.feishu.cn/base/<app_token>?table=<table_id>",
            required=True,
        ),
        DataInput(
            name="records_data",
            display_name="输入数据(Data)",
            info="上游 Data 端口传入记录列表或包含 data/records 列表的对象",
        ),
    ]

    outputs = [
        Output(display_name="结果", name="result", method="run"),
    ]

    # 固定开放平台域名
    OPEN_BASE = "https://open.feishu.cn"

    def run(self) -> Data:
        try:
            # 1) 前台必填凭证
            app_id = (self.app_id or "").strip()
            app_secret = (self.app_secret or "").strip()
            if not app_id or not app_secret:
                raise RuntimeError("缺少 App 凭证：请填写 FEISHU_APP_ID 与 FEISHU_APP_SECRET")

            self.status = "获取租户令牌..."
            access_token = self._get_tenant_access_token(app_id, app_secret, self.OPEN_BASE)

            # 2) 解析 URL -> app_token / 可能的 table_id
            self.status = "解析飞书链接..."
            feishu_url = self.feishu_url.strip()
            app_token, url_table_id = None, None

            if "wiki" in feishu_url:
                # 官方要求：wiki 链接中的 token 是节点 token，需要先映射出实际云文档 token
                self.status = "检测到 Wiki 链接，解析节点映射..."
                try:
                    from urllib.parse import urlparse
                    p = urlparse(feishu_url)
                    parts = [seg for seg in p.path.split("/") if seg]
                    if len(parts) < 2 or parts[0] != "wiki":
                        raise RuntimeError("Wiki 链接格式不正确，应为 /wiki/<node_token>")
                    wiki_token = parts[1]
                except Exception as e:
                    raise RuntimeError(f"解析 Wiki 链接失败：{e}")

                # 通过官方接口将 wiki 节点 token 映射为实际云文档 token
                obj_type, obj_token = self._get_obj_token_from_wiki_node(access_token, wiki_token, self.OPEN_BASE)
                if obj_type == "bitable" and obj_token:
                    # 对于 bitable，obj_token 即为 app_token
                    app_token = obj_token
                    # 若 Wiki 链接携带 ?table= 参数，作为回退目标表
                    try:
                        from urllib.parse import parse_qs
                        q = parse_qs(p.query)
                        table_q = q.get("table", [])
                        if table_q:
                            url_table_id = table_q[0]
                        else:
                            url_table_id = None
                    except Exception:
                        url_table_id = None
                else:
                    # 非 bitable（如 docx/sheet 的 Wiki 页面），尝试读取文档内容提取表格链接
                    if not obj_token:
                        raise RuntimeError(f"Wiki 节点未返回有效 obj_token，类型为 {obj_type or '未知'}。")
                    self.status = "Wiki 节点为文档类型，尝试从文档中提取表格链接..."
                    bitable_url = self._get_bitable_url_from_docx(access_token, obj_token, self.OPEN_BASE)
                    if not bitable_url:
                        raise RuntimeError(f"未能在 Wiki 文档中找到多维表格链接（obj_type={obj_type}）。")
                    # 从提取到的链接解析 app_token/table_id
                    app_token, url_table_id = self._parse_feishu_url(bitable_url)
                    if not app_token:
                        raise RuntimeError("已从 Wiki 文档找到链接，但无法解析出 App Token。")
            else:
                app_token, url_table_id = self._parse_feishu_url(feishu_url)

            if not app_token:
                raise RuntimeError("无法从链接中提取 Base App Token，请检查链接格式或 Wiki 内容。")

            # 3) 收集/格式化记录
            self.status = "解析输入记录..."
            records = self._collect_records_from_data(self.records_data)
            formatted = self._format_text_only(records) if records else []
            written_count = 0

            # 4) 首选：创建新表
            try:
                self.status = "创建新表..."
                table_id = self._create_bitable_table(access_token, app_token, self.OPEN_BASE, formatted)

                if formatted:
                    self.status = f"写入 {len(formatted)} 条记录..."
                    self._batch_add_records(access_token, app_token, table_id, formatted, self.OPEN_BASE, batch_size=50)
                    written_count = len(formatted)

                link = self._build_table_link(app_token, table_id)
                msg = f"新表创建成功，已写入 {written_count} 条记录"
                self.status = msg
                return Data(data={
                    "status": "success",
                    "message": msg,
                    "app_token": app_token,
                    "table_id": table_id,
                    "table_link": link,
                    "written_count": written_count,
                })
            except Exception as create_err:
                # 5) 回退：若 URL 带现有 table_id，则尝试写入它
                if url_table_id:
                    self.status = f"创建新表失败：{create_err}；回退写入现有表 {url_table_id}..."
                    try:
                        if formatted:
                            self._ensure_fields(access_token, app_token, url_table_id, formatted, self.OPEN_BASE)
                            self._batch_add_records(access_token, app_token, url_table_id, formatted, self.OPEN_BASE, batch_size=50)
                            written_count = len(formatted)
                        link = self._build_table_link(app_token, url_table_id)
                        msg = f"创建失败已回退：向现有表写入 {written_count} 条记录"
                        self.status = msg
                        return Data(data={
                            "status": "success",
                            "message": msg,
                            "app_token": app_token,
                            "table_id": url_table_id,
                            "table_link": link,
                            "written_count": written_count,
                        })
                    except Exception as write_err:
                        self.status = f"失败：创建与回退写入均失败（{write_err}）"
                        link = self._build_table_link(app_token, url_table_id)
                        return Data(data={
                            "status": "failure",
                            "message": f"创建新表失败：{create_err}；回退写入失败：{write_err}",
                            "app_token": app_token,
                            "table_id": url_table_id,
                            "table_link": link,
                            "written_count": 0,
                        })
                # 无现有 table_id 可回退
                raise

        except Exception as e:
            self.status = f"失败：{e}"
            fallback_link = None
            try:
                at, tid = self._parse_feishu_url(self.feishu_url)
                if at and tid:
                    fallback_link = self._build_table_link(at, tid)
            except:
                pass
            return Data(data={
                "status": "failure",
                "message": str(e),
                "app_token": None,
                "table_id": None,
                "table_link": fallback_link,
                "written_count": 0,
            })

    # ======== 辅助方法 ========
    def _get_tenant_access_token(self, app_id: str, app_secret: str, open_base: str) -> str:
        url = f"{open_base}/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"获取租户令牌失败: HTTP {resp.status_code}, 响应: {resp.text}")
        data = resp.json()
        if data.get("code") == 0:
            return data["tenant_access_token"]
        raise RuntimeError(f"获取租户令牌失败: {data}")

    def _get_obj_token_from_wiki_node(self, access_token: str, wiki_token: str, open_base: str) -> Tuple[str | None, str | None]:
        """
        使用官方接口：GET /open-apis/wiki/v2/spaces/get_node
        将 wiki 节点的 token 映射为实际云文档的 obj_token 与 obj_type。
        - 当 obj_type == 'bitable' 时，obj_token 即为多维表格的 app_token。
        """
        url = f"{open_base}/open-apis/wiki/v2/spaces/get_node"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=utf-8"}
        params = {"token": wiki_token}
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"获取 Wiki 节点信息失败: HTTP {resp.status_code}, 响应: {resp.text}")
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError("获取 Wiki 节点信息失败：响应不是 JSON")
        if data.get("code") != 0:
            raise RuntimeError(f"获取 Wiki 节点信息失败: {data}")
        data_block = data.get("data", {}) or {}
        node = data_block.get("node") or data_block
        # 官方返回字段可能为 obj_type/obj_token，做兼容处理
        obj_type = node.get("obj_type") or node.get("type")
        obj_token = node.get("obj_token") or node.get("token")
        return obj_type, obj_token

    def _get_bitable_url_from_wiki(self, access_token: str, wiki_url: str, open_base: str) -> str | None:
        from urllib.parse import urlparse
        
        self.status = f"从 Wiki URL 解析文档 ID: {wiki_url}"
        try:
            parsed_url = urlparse(wiki_url)
            path_parts = [part for part in parsed_url.path.split('/') if part]
            # Expects format like /wiki/wikcnxxxxxxxx
            if len(path_parts) < 2 or path_parts[0] != 'wiki':
                self.status = "Wiki URL 格式不正确，应为 /wiki/<doc_id>"
                return None
            doc_id = path_parts[1]
        except Exception as e:
            self.status = f"解析 Wiki URL 失败: {e}"
            return None

        self.status = f"获取 Wiki 内容 (ID: {doc_id})..."
        url = f"{open_base}/open-apis/docx/v1/documents/{doc_id}/raw_content"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                self.status = f"获取 Wiki 内容失败: HTTP {resp.status_code}, {resp.text}"
                return None
        except requests.exceptions.RequestException as e:
            self.status = f"获取 Wiki 内容 API 请求失败: {e}"
            return None

        data = resp.json()
        if data.get("code") != 0:
            self.status = f"获取 Wiki 内容 API 错误: {data.get('msg') or resp.text}"
            return None

        content = data.get("data", {}).get("content", "")
        if not content:
            self.status = "Wiki 文档内容为空"
            return None

        self.status = "在 Wiki 内容中搜索表格链接..."
        # Regex to find a Feishu Bitable URL (e.g., https://*.feishu.cn/base/app_token...)
        match = re.search(r'https?://[a-zA-Z0-9\.-]+\.feishu\.cn/base/[a-zA-Z0-9]+(?:/table/[a-zA-Z0-9]+)?(?:[?&][^=\s]+=[^&\s]+)*', content)
        if match:
            found_url = match.group(0)
            self.status = f"在 Wiki 中找到表格链接: {found_url}"
            return found_url
        
        self.status = "在 Wiki 内容中未找到飞书表格链接"
        return None

    def _get_bitable_url_from_docx(self, access_token: str, doc_token: str, open_base: str) -> str | None:
        """读取 docx 文档原始内容，提取其中的多维表格链接"""
        url = f"{open_base}/open-apis/docx/v1/documents/{doc_token}/raw_content"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                return None
        except requests.exceptions.RequestException:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        if data.get("code") != 0:
            return None
        content = data.get("data", {}).get("content", "")
        if not content:
            return None
        match = re.search(r'https?://[a-zA-Z0-9\.-]+\.feishu\.cn/base/[a-zA-Z0-9]+(?:/table/[a-zA-Z0-9]+)?(?:[?&][^=\s]+=[^&\s]+)*', content)
        if match:
            return match.group(0)
        return None

    def _create_bitable_table(self, access_token: str, app_token: str, open_base: str, sample_records: List[Dict] | None = None) -> str:
        url = f"{open_base}/open-apis/bitable/v1/apps/{app_token}/tables"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        table_name = f"新建表格-{time.strftime('%Y%m%d%H%M%S')}"
        ordered_keys: List[str] = []
        if sample_records:
            seen: set[str] = set()
            for rec in sample_records:
                if isinstance(rec, dict):
                    for k in rec.keys():
                        if k not in seen:
                            ordered_keys.append(k)
                            seen.add(k)
        fields_payload = [{"type": 1, "field_name": k} for k in ordered_keys]
        payload = {"table": {"name": table_name, "fields": fields_payload}}
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"创建表格失败: HTTP {resp.status_code}, 响应: {resp.text}")
        data = resp.json()
        if data.get("code") == 0:
            return data["data"]["table_id"]
        raise RuntimeError(f"创建表格失败: {data}")

    def _get_table_fields(self, access_token: str, app_token: str, table_id: str, open_base: str) -> List[Dict]:
        url = f"{open_base}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"获取字段信息失败: HTTP {resp.status_code}, 响应: {resp.text}")
        data = resp.json()
        if data.get("code") == 0:
            return data.get("data", {}).get("items", [])
        raise RuntimeError(f"获取字段信息失败: {data}")

    def _create_field(self, access_token: str, app_token: str, table_id: str, field_name: str, open_base: str, field_type: int = 1) -> str:
        url = f"{open_base}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        payload = {"field_name": field_name, "type": field_type}
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(f"创建字段失败: HTTP {resp.status_code}, 响应: {resp.text}")
        data = resp.json()
        if data.get("code") == 0:
            return data.get("data", {}).get("field", {}).get("field_id", "")
        raise RuntimeError(f"创建字段失败: {data}")

    def _ensure_fields(self, access_token: str, app_token: str, table_id: str, sample_records: List[Dict], open_base: str):
        items = self._get_table_fields(access_token, app_token, table_id, open_base)
        existing = {it.get("field_name") for it in items if it.get("field_name")}
        all_keys: set[str] = set()
        for rec in sample_records:
            if isinstance(rec, dict):
                all_keys.update(rec.keys())
        missing = [k for k in all_keys if k not in existing]
        for field_name in missing:
            try:
                self._create_field(access_token, app_token, table_id, field_name, open_base, field_type=1)
            except Exception as e:
                self.status = f"创建字段失败：{field_name}，错误：{e}"

    def _batch_add_records(self, access_token: str, app_token: str, table_id: str, records: List[Dict], open_base: str, batch_size: int = 50):
        url = f"{open_base}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        total = len(records)
        for i in range(0, total, batch_size):
            chunk = records[i:i+batch_size]
            payload = {"records": [{"fields": r} for r in chunk]}
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code != 200:
                raise RuntimeError(f"写入记录失败: HTTP {resp.status_code}, 响应: {resp.text}")
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"写入记录失败: {data}")

    def _build_table_link(self, app_token: str, table_id: str) -> str:
        return f"https://www.feishu.cn/base/{app_token}/table/{table_id}"

    def _parse_feishu_url(self, url: str) -> Tuple[str | None, str | None]:
        try:
            from urllib.parse import urlparse, parse_qs
            p = urlparse(url)
            parts = [seg for seg in p.path.split("/") if seg]
            app_token = None
            table_id = None
            if len(parts) >= 2 and parts[0] == "base":
                app_token = parts[1]
                if len(parts) >= 4 and parts[2] == "table":
                    table_id = parts[3]
            if not table_id:
                q = parse_qs(p.query)
                table_q = q.get("table", [])
                if table_q:
                    table_id = table_q[0]
            return app_token, table_id
        except Exception:
            return None, None

    def _collect_records_from_data(self, records_data: Any) -> List[Dict]:
        data_list: List[Dict] = []
        if records_data:
            payload: Any = None
            text: str | None = None
            try:
                payload = records_data.data if hasattr(records_data, "data") else None
                if hasattr(records_data, "get_text"):
                    text = records_data.get_text()
            except Exception:
                payload = None

            if isinstance(payload, dict):
                if "value" in payload and isinstance(payload["value"], dict) and "data" in payload["value"]:
                    data_list = payload["value"]["data"] or []
                elif "data" in payload and isinstance(payload["data"], list):
                    data_list = payload["data"] or []
                elif isinstance(payload.get("records"), list):
                    data_list = payload["records"] or []
                # 新增：支持顶层 results 以及 value.results
                elif isinstance(payload.get("results"), list):
                    data_list = payload["results"] or []
                elif "value" in payload and isinstance(payload["value"], dict) and isinstance(payload["value"].get("results"), list):
                    data_list = payload["value"]["results"] or []
            elif isinstance(payload, list):
                data_list = payload

            if not data_list and text:
                try:
                    obj = json.loads(text)
                    if isinstance(obj, dict):
                        if "value" in obj and isinstance(obj["value"], dict) and "data" in obj["value"]:
                            data_list = obj["value"]["data"] or []
                        elif "data" in obj and isinstance(obj["data"], list):
                            data_list = obj["data"] or []
                        # 新增：支持文本 JSON 中的 results / value.results
                        elif isinstance(obj.get("results"), list):
                            data_list = obj["results"] or []
                        elif "value" in obj and isinstance(obj["value"], dict) and isinstance(obj["value"].get("results"), list):
                            data_list = obj["value"]["results"] or []
                except Exception:
                    pass

        return [r for r in data_list if isinstance(r, dict)]

    def _format_text_only(self, records: List[Dict]) -> List[Dict]:
        formatted: List[Dict] = []
        for rec in records:
            new_fields = {}
            for k, v in rec.items():
                new_fields[k] = v if isinstance(v, str) else ("" if v is None else str(v))
            formatted.append(new_fields)
        return formatted