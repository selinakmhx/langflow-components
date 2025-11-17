import json
import time
import random
from typing import Any, Dict, List, Optional

import requests


class XiaohongshuLocalSearch:
    """
    一个本地可运行的小红书搜索脚本，用于根据关键词采集笔记。

    功能：
    - 按关键词搜索笔记，实现 v3 -> v2 的失败回退。
    - 可选获取作者详细信息，实现 v4 -> v3 的失败回退。
    - 获取笔记详情，实现 v7 -> v3 的失败回退。
    - 包含完整的网络请求、重试与错误处理逻辑。
    """

    # API 环境配置
    ENV_BASE: Dict[str, str] = {
        "中国区": "http://47.117.133.51:30015",
        "全球区": "https://api.justoneapi.com",
    }

    # API 路径
    PATHS: Dict[str, str] = {
        "user_info_v4": "/api/xiaohongshu/get-user/v4",
        "user_info_v3": "/api/xiaohongshu/get-user/v3",
        "search_note_v3": "/api/xiaohongshu/search-note/v3",
        "search_note_v2": "/api/xiaohongshu/search-note/v2",
        "note_detail_v7": "/api/xiaohongshu/get-note-detail/v7",
        "note_detail_v3": "/api/xiaohongshu/get-note-detail/v3",
    }

    # 错误码中文映射
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

    def __init__(self, token: str, environment: str = "中国区"):
        """
        初始化搜索器。

        :param token: Just One API 的 Token。
        :param environment: API 环境，"中国区" 或 "全球区"。
        """
        if not token or token == "YOUR_TOKEN":
            raise ValueError("必须提供有效的 Just One API Token。")
        self.token = token
        self.base_url = self.ENV_BASE.get(environment, self.ENV_BASE["中国区"])
        self.metrics = {}  # 用于记录统计信息

        # 网络请求参数
        self.REQUEST_PRE_DELAY_MS = 800
        self.REQUEST_TIMEOUT_SECONDS = 75
        self.REQUEST_RETRY_ATTEMPTS = 3
        self.REQUEST_RETRY_BACKOFF_BASE_MS = 600
        self.REQUEST_RETRY_BACKOFF_JITTER_MS = 400

    def _mask_token(self) -> str:
        """隐藏 Token，用于日志输出。"""
        if len(self.token) <= 8:
            return "***"
        return f"{self.token[:3]}***{self.token[-4:]}"

    def _http_get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        发起 GET 请求的底层封装，包含完整的重试和错误处理逻辑。
        """
        url = f"{self.base_url}{path}"
        query = {"token": self.token, **{k: v for k, v in params.items() if v is not None and v != ""}}

        # 请求前固定等待
        if self.REQUEST_PRE_DELAY_MS > 0:
            time.sleep(self.REQUEST_PRE_DELAY_MS / 1000.0)

        for attempt_idx in range(1, self.REQUEST_RETRY_ATTEMPTS + 1):
            start = time.perf_counter()
            try:
                resp = requests.get(url, params=query, timeout=self.REQUEST_TIMEOUT_SECONDS)
                duration_ms = int((time.perf_counter() - start) * 1000)
                self.metrics.setdefault("request_durations", {}).setdefault(path, []).append(duration_ms)

                try:
                    body = resp.json()
                except json.JSONDecodeError:
                    body = None

                # 注入中文错误信息
                if isinstance(body, dict) and body.get("code") in self.ERROR_CODE_MAP:
                    body["message_cn"] = self.ERROR_CODE_MAP[body["code"]]

                # 成功或无需重试的业务错误
                if (isinstance(body, dict) and body.get("code") == 0) or resp.status_code not in [429, 500, 502, 503, 504]:
                    return body if isinstance(body, dict) else {"code": -1, "message": "Invalid JSON response", "message_cn": "无效的JSON响应"}

                # 需要重试的错误
                if attempt_idx < self.REQUEST_RETRY_ATTEMPTS:
                    backoff_ms = self.REQUEST_RETRY_BACKOFF_BASE_MS * (2 ** (attempt_idx - 1)) + random.randint(0, self.REQUEST_RETRY_BACKOFF_JITTER_MS)
                    time.sleep(backoff_ms / 1000.0)
                    continue

                return body  # 返回最后一次尝试的错误信息

            except requests.RequestException as e:
                if attempt_idx < self.REQUEST_RETRY_ATTEMPTS:
                    backoff_ms = self.REQUEST_RETRY_BACKOFF_BASE_MS * (2 ** (attempt_idx - 1)) + random.randint(0, self.REQUEST_RETRY_BACKOFF_JITTER_MS)
                    time.sleep(backoff_ms / 1000.0)
                    continue
                
                return {
                    "code": -1,
                    "message": f"Request error: {e}",
                    "message_cn": "网络请求异常",
                    "error": {"type": "network_error", "path": path, "params": {**params, "token": self._mask_token()}},
                }
        return {"code": -1, "message": "Max retries reached", "message_cn": "已达到最大重试次数"}


    def _get_note_detail(self, note_id: str) -> Dict[str, Any]:
        """获取笔记详情，实现 v7 -> v3 回退。"""
        params = {"noteId": note_id}
        resp7 = self._http_get(self.PATHS["note_detail_v7"], params)
        self.metrics.setdefault("version_choice", []).append({"api": "note_detail", "prefer": "v7", "result_code": resp7.get("code")})
        if resp7.get("code") == 0:
            return resp7
        
        # 如果 v7 失败，则回退到 v3
        resp3 = self._http_get(self.PATHS["note_detail_v3"], params)
        self.metrics.setdefault("version_choice", []).append({"api": "note_detail", "fallback": "v3", "result_code": resp3.get("code")})
        return resp3

    def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """获取用户信息，实现 v4 -> v3 回退。"""
        params = {"userId": user_id}
        resp4 = self._http_get(self.PATHS["user_info_v4"], params)
        self.metrics.setdefault("version_choice", []).append({"api": "user_info", "prefer": "v4", "result_code": resp4.get("code")})
        if resp4.get("code") == 0:
            return resp4

        # 如果 v4 失败，则回退到 v3
        resp3 = self._http_get(self.PATHS["user_info_v3"], params)
        self.metrics.setdefault("version_choice", []).append({"api": "user_info", "fallback": "v3", "result_code": resp3.get("code")})
        return resp3

    @staticmethod
    def _ensure_note_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """从搜索结果中提取并规整化单个笔记对象。"""
        if not isinstance(item, dict):
            return {}
        if item.get("model_type") == "ads":
            return (item.get("ads") or {}).get("note") or {}
        if item.get("model_type") == "note":
            return item.get("note") or item
        return item.get("note") or item

    def search_notes_by_keyword(
        self,
        keyword: str,
        start_page: int = 1,
        end_page: int = 1,
        sort: str = "general",
        note_type: str = "_0",
        include_author_detail: bool = False,
        include_note_detail: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        按关键词搜索笔记的主函数。

        :param keyword: 搜索关键词。
        :param start_page: 开始页码。
        :param end_page: 结束页码。
        :param sort: 排序方式。
        :param note_type: 笔记类型。
        :param include_author_detail: 是否获取作者详细信息。
        :param include_note_detail: 是否获取笔记详情（正文）。
        :return: 处理后的笔记列表。
        """
        all_processed_notes = []
        for page in range(start_page, end_page + 1):
            print(f"--- 开始采集第 {page} 页 ---")
            
            # 优先调用 v3
            search_params = {"keyword": keyword, "page": page, "sort": sort, "noteType": note_type}
            search_resp = self._http_get(self.PATHS["search_note_v3"], search_params)
            self.metrics.setdefault("version_choice", []).append({"api": "search_note", "prefer": "v3", "result_code": search_resp.get("code")})

            # v3 失败则回退到 v2
            if search_resp.get("code") != 0:
                print("search-note/v3 调用失败，尝试回退到 v2...")
                search_resp = self._http_get(self.PATHS["search_note_v2"], search_params)
                self.metrics.setdefault("version_choice", []).append({"api": "search_note", "fallback": "v2", "result_code": search_resp.get("code")})

            if search_resp.get("code") != 0:
                print(f"第 {page} 页采集失败: {search_resp.get('message_cn', search_resp.get('message'))}")
                continue

            items = (search_resp.get("data") or {}).get("items") or []
            if not items:
                print(f"第 {page} 页没有找到更多笔记。")
                break

            for item in items:
                note = self._ensure_note_item(item)
                if not note or not note.get("id"):
                    continue

                user = note.get("user") or {}
                processed_note = {
                    "笔记ID": note.get("id"),
                    "笔记链接": f"https://www.xiaohongshu.com/explore/{note.get('id')}",
                    "标题": note.get("title") or note.get("display_title"),
                    "摘要": note.get("desc"),
                    "笔记类型": note.get("type"),
                    "点赞数": note.get("liked_count"),
                    "收藏数": note.get("collected_count"),
                    "作者昵称": user.get("nickname"),
                    "作者ID": user.get("userid"),
                    "原始搜索结果": note,
                }

                # 获取笔记详情
                if include_note_detail:
                    detail_resp = self._get_note_detail(note["id"])
                    if detail_resp.get("code") == 0:
                        # 提取正文
                        desc_list = (detail_resp.get("data") or [{}])[0].get("note_list")
                        if desc_list:
                            processed_note["笔记正文"] = desc_list[0].get("desc")
                        processed_note["笔记详情"] = detail_resp.get("data")
                    else:
                        processed_note["笔记详情"] = {"error": detail_resp}

                # 获取作者信息
                if include_author_detail and user.get("userid"):
                    user_info_resp = self._get_user_info(user["userid"])
                    if user_info_resp.get("code") == 0:
                        processed_note["作者详细信息"] = user_info_resp.get("data")
                    else:
                        processed_note["作者详细信息"] = {"error": user_info_resp}
                
                all_processed_notes.append(processed_note)
                print(f"  - 已处理笔记: {processed_note['标题']}")

        return all_processed_notes


if __name__ == "__main__":
    # --- 配置 ---
    # 请在这里填入你的真实 Token
    API_TOKEN = "rrZQl9kQ"
    # 搜索关键词
    SEARCH_KEYWORD = "猫猫"
    # 是否获取作者详细信息
    GET_AUTHOR_DETAIL = True

    print("--- 任务开始 ---")
    print(f"Token: {'*' * 8}")
    print(f"关键词: {SEARCH_KEYWORD}")
    print(f"是否获取作者详情: {GET_AUTHOR_DETAIL}")
    
    # 初始化并运行搜索
    searcher = XiaohongshuLocalSearch(token=API_TOKEN)
    
    try:
        notes_data = searcher.search_notes_by_keyword(
            keyword=SEARCH_KEYWORD,
            start_page=1,
            end_page=1,
            include_author_detail=GET_AUTHOR_DETAIL
        )

        # 将结果保存到文件
        output_filename = "xhs_search_results.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(notes_data, f, ensure_ascii=False, indent=4)

        print(f"--- 任务完成 ---")
        print(f"成功采集 {len(notes_data)} 条笔记。")
        print(f"结果已保存到文件: {output_filename}")
        
        # 打印统计信息
        print("\n--- 统计信息 ---")
        print(json.dumps(searcher.metrics, ensure_ascii=False, indent=4))

    except ValueError as e:
        print(f"错误: {e}")
    except Exception as e:
        print(f"发生意外错误: {e}")