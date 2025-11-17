import json
import sys
import os

# 将项目根目录加入模块搜索路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from xiaohongshu_rednote import XiaohongshuRedNote


def main():
    comp = XiaohongshuRedNote()
    # 设置为用户笔记模式，模拟环境与输入
    comp.mode = "按用户信息采集笔记"
    comp.environment = "中国区"
    comp.token = "DUMMY_TOKEN"  # 非空以绕过早期校验
    comp.xhs_user_id = "u123"
    comp.user_notes_last_cursor = ""
    comp.force_user_detail = False

    # 打桩 _http_get，避免真实网络请求
    def fake_http_get(path: str, params: dict):
        if "get-user-note-list" in path:
            return {
                "code": 0,
                "data": {
                    "notes": [
                        {
                            "id": "note_1",
                            "noteId": "note_1",
                            "desc": "列表正文（无需详情）",
                            "display_title": "标题A",
                            "user": {"nickname": "Alice", "userid": "u123"},
                            "timestamp": 1730000000,
                            "images_list": [],
                        }
                    ],
                    "has_more": False,
                    "cursor": "",
                },
            }
        if "get-note-detail" in path:
            return {"code": 0, "data": {"note_list": [{"desc": "详情正文"}]}}
        if "get-user" in path:
            return {"code": 0, "data": {"userid": "u123", "share_link": "https://www.xiaohongshu.com/user/profile/u123"}}
        if "search-note" in path:
            return {"code": 0, "data": {"list": []}}
        if "get-note-comment" in path or "get-note-sub-comment" in path:
            return {"code": 0, "data": {"comments": []}}
        return {"code": 0, "data": {}}

    comp._http_get = fake_http_get  # 注入桩方法

    try:
        data = comp.build_output()
        # Data 对象可能包含 .data 属性；尽量安全打印
        payload = getattr(data, "data", data)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("OK: build_output 执行完成，无 UnboundLocalError")
    except Exception as e:
        print("ERROR:", e)


if __name__ == "__main__":
    main()