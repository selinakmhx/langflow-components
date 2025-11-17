#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
本地脚本：按用户采集信息（小红书 / Just One API）

功能：
- 组合调用 用户信息(v4→v3) 与 用户笔记列表(v4→v2)，可选详情补全
- 分页（基于 cursor/has_more），默认采集 1 页
- 中文键输出，包含简单错误分类与请求耗时统计

运行示例：
python3 py/user_notes_collect.py \
  --token rrZQl9kQ --user-id 636519f2000000001f019e57 --pages 1 --env 全球区

说明：
- 仅作为本地测试脚本，参考 components/pybug/xhs.py 的接口参数与调用顺序
- 不依赖 langflow 等框架，直接 requests 发起 HTTP GET
"""

import argparse
import json
import re
import time
from typing import Any, Dict, List, Optional

import requests


# 环境地址
ENV_BASE: Dict[str, str] = {
    "中国区": "http://47.117.133.51:30015",
    "全球区": "https://api.justoneapi.com",
}

# 接口路径映射（与参考组件保持一致）
PATHS: Dict[str, str] = {
    "user_info_v4": "/api/xiaohongshu/get-user/v4",
    "user_info_v3": "/api/xiaohongshu/get-user/v3",
    "user_note_list_v4": "/api/xiaohongshu/get-user-note-list/v4",
    "user_note_list_v2": "/api/xiaohongshu/get-user-note-list/v2",
    "note_detail_v7": "/api/xiaohongshu/get-note-detail/v7",
    "note_detail_v3": "/api/xiaohongshu/get-note-detail/v3",
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


def _mask_token(token: Optional[str]) -> str:
    t = token or ""
    if len(t) <= 8:
        return "***"
    return f"{t[:3]}***{t[-4:]}"


def _classify_error(http_status: Optional[int], body: Optional[Dict[str, Any]]) -> str:
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
    if isinstance(code, int) and code == 100:
        return "auth_error"
    up = msg.upper()
    if "TOKEN" in up and ("INVALID" in up or "UNACTIVATE" in up):
        return "auth_error"
    if isinstance(code, int) and code != 0:
        return "api_error"
    return ""


def http_get(base_url: str, path: str, params: Dict[str, Any], token: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{base_url}{path}"
    query = {"token": token, **{k: v for k, v in params.items() if v not in (None, "")}}
    start = time.perf_counter()
    try:
        resp = requests.get(url, params=query, timeout=60)
        duration_ms = int((time.perf_counter() - start) * 1000)
        metrics.setdefault("request_durations", {}).setdefault(path, []).append(duration_ms)
        status = resp.status_code
        try:
            body = resp.json()
        except json.JSONDecodeError:
            body = None

        if isinstance(body, dict):
            code = body.get("code")
            if isinstance(code, int) and code in ERROR_CODE_MAP:
                body["message_cn"] = ERROR_CODE_MAP[code]
        if isinstance(body, dict) and body.get("code") == 0:
            return body

        error_type = _classify_error(status, body if isinstance(body, dict) else None)
        debug_req = {
            "path": path,
            "url": resp.url,
            "环境": base_url,
            "params": {**{k: v for k, v in params.items() if v not in (None, "")}, "token": _mask_token(token)},
            "http_status": status,
            "duration_ms": duration_ms,
        }
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
        metrics.setdefault("request_durations", {}).setdefault(path, []).append(duration_ms)
        debug_req = {
            "path": path,
            "url": f"{base_url}{path}",
            "环境": base_url,
            "params": {**{k: v for k, v in params.items() if v not in (None, "")}, "token": _mask_token(token)},
            "http_status": None,
            "duration_ms": duration_ms,
        }
        return {
            "code": -1,
            "message": f"request error: {e}",
            "message_cn": "网络请求异常",
            "data": None,
            "error": {"type": "network_error", **debug_req},
        }


def get_user_notes_page(base_url: str, token: str, user_id: str, last_cursor: Optional[str], metrics: Dict[str, Any]) -> Dict[str, Any]:
    params = {"userId": user_id}
    if last_cursor:
        params["lastCursor"] = last_cursor
    resp4 = http_get(base_url, PATHS["user_note_list_v4"], params, token, metrics)
    metrics.setdefault("version_choice", []).append({"api": "user_note_list", "prefer": "v4", "result_code": resp4.get("code")})
    if resp4.get("code") == 0:
        return resp4
    resp2 = http_get(base_url, PATHS["user_note_list_v2"], params, token, metrics)
    metrics.setdefault("version_choice", []).append({"api": "user_note_list", "fallback": "v2", "result_code": resp2.get("code")})
    return resp2


def get_note_detail(base_url: str, token: str, note_id: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
    resp7 = http_get(base_url, PATHS["note_detail_v7"], {"noteId": note_id}, token, metrics)
    metrics.setdefault("version_choice", []).append({"api": "note_detail", "prefer": "v7", "result_code": resp7.get("code")})
    if resp7.get("code") == 0:
        return resp7
    resp3 = http_get(base_url, PATHS["note_detail_v3"], {"noteId": note_id}, token, metrics)
    metrics.setdefault("version_choice", []).append({"api": "note_detail", "fallback": "v3", "result_code": resp3.get("code")})
    return resp3


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


def _normalize_ts(ts: Any) -> Optional[int]:
    try:
        if ts is None:
            return None
        val = int(ts)
        # 毫秒转秒
        if val > 10_000_000_000:
            return val // 1000
        return val
    except Exception:
        return None


def _extract_tags_from_text(text: Optional[str]) -> List[str]:
    if not isinstance(text, str) or not text:
        return []
    tags = re.findall(r"#([^#]+)#", text)
    return [t.strip() for t in tags if t.strip()]


def collect_user_notes(base_url: str, token: str, user_id: str, pages: int = 1, force_detail: bool = False) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}

    result: Dict[str, Any] = {
        "meta": {
            "环境": base_url,
        },
        "数据": [],
        "版本选择": metrics.get("version_choice", []),
    }

    last_cursor: Optional[str] = None
    total_notes = 0
    max_pages = pages if pages > 0 else 100  # pages=0时，最多采集100页作为保护

    for page_idx in range(max_pages):
        resp = get_user_notes_page(base_url, token, user_id, last_cursor, metrics)
        block: Dict[str, Any] = {
            "页码": page_idx + 1,
            "用户ID": user_id,
            "原始": resp,
            "笔记": [],
        }

        if resp.get("code") == 0 and isinstance(resp.get("data"), dict):
            d = resp["data"]
            items = d.get("notes") or d.get("list") or d.get("items") or []
            for n in items:
                note_id = (n.get("noteId") or n.get("id") or "")
                ts = _normalize_ts(
                    n.get("timestamp")
                    or n.get("update_time")
                    or n.get("publishTime")
                    or n.get("time")
                    or n.get("create_time")
                )
                obj: Dict[str, Any] = {
                    "笔记ID": note_id,
                    "笔记链接": f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else "",
                    "标题": n.get("display_title") or n.get("title"),
                    "正文": None,
                    "发布时间": ts,
                    "点赞数": n.get("likes") or n.get("liked_count"),
                    "评论数": n.get("comments_count"),
                    "收藏数": n.get("collected_count"),
                }

                list_desc = n.get("desc")
                need_detail = force_detail or not (isinstance(list_desc, str) and list_desc.strip())
                if not need_detail:
                    obj["正文"] = list_desc
                    obj["标签"] = _extract_tags_from_text(list_desc)
                elif note_id:
                    detail_resp = get_note_detail(base_url, token, note_id, metrics)
                    content_text = _extract_note_desc(detail_resp, n)
                    if content_text:
                        obj["正文"] = content_text
                        obj["标签"] = _extract_tags_from_text(content_text)
                    obj["详情"] = detail_resp

                block["笔记"].append(obj)
            total_notes += len(block["笔记"])

            block["还有更多"] = d.get("has_more")
            block["下一页游标"] = d.get("cursor")
            last_cursor = d.get("cursor") if d.get("has_more") else None
        else:
            # 将错误提升到顶层错误列表，便于排查
            err = resp.get("error") or {"类型": "unknown", "消息": resp.get("message")}
            result.setdefault("错误列表", []).append({"步骤": f"用户笔记 第{page_idx+1}页", "错误": err})

        result["数据"].append(block)

        # 无更多或下一页游标缺失，则提前结束分页
        if not (last_cursor and block.get("还有更多")):
            break

    # 请求耗时统计
    durations: Dict[str, Any] = {}
    for path, arr in metrics.get("request_durations", {}).items():
        if not arr:
            continue
        durations[path] = {
            "次数": len(arr),
            "最短耗时ms": min(arr),
            "最长耗时ms": max(arr),
            "平均耗时ms": int(sum(arr) / len(arr)),
        }
    result.setdefault("meta", {}).update({
        "请求耗时": durations,
        "总笔记数": total_notes,
    })

    return result


def main():
    parser = argparse.ArgumentParser(description="按用户采集信息（小红书 / Just One API）")
    parser.add_argument("--env", choices=list(ENV_BASE.keys()), default="中国区", help="环境：中国区 / 全球区")
    parser.add_argument("--token", default="rrZQl9kQ", help="Just One API Token（测试默认值 rrZQl9kQ）")
    parser.add_argument("--user-id", default="636519f2000000001f019e57", help="小红书用户UID（测试默认值 636519f2000000001f019e57）")
    parser.add_argument("--pages", type=int, default=1, help="最多采集页数（基于 has_more/cursor 分页）")
    parser.add_argument("--force-detail", action="store_true", help="是否对列表每条笔记都调用详情以补全正文")
    parser.add_argument("--output", help="将结果保存到指定 JSON 文件路径")
    args = parser.parse_args()

    base_url = ENV_BASE.get(args.env, ENV_BASE["全球区"])  # 默认全球区域
    result = collect_user_notes(base_url, args.token, args.user_id, pages=max(1, args.pages), force_detail=args.force_detail)
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"结果已保存到：{args.output}")
        except Exception as e:
            print(f"错误：无法写入文件 {args.output} - {e}")
            print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()