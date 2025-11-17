# -*- coding: utf-8 -*-

import json
import sys
import time
import re
import io
import contextlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from urllib import request, error
import pandas as pd

from langflow.custom import Component
from langflow.io import MessageTextInput, IntInput, DropdownInput, BoolInput, Output
from langflow.schema import Data


class XiaohongshuScraper(Component):
    display_name = "小红书爬虫"
    description = "小红书数据爬取组件，支持关键词搜索和数据导出"
    icon = "🔍"

    inputs = [
        MessageTextInput(
            name="keyword",
            display_name="搜索关键词",
            info="要搜索的关键词",
            value="项链"
        ),
        IntInput(
            name="start_page",
            display_name="开始页数",
            info="爬取的起始页数",
            value=1
        ),
        IntInput(
            name="end_page", 
            display_name="结束页数",
            info="爬取的结束页数",
            value=3
        ),
        DropdownInput(
            name="sort_type",
            display_name="排序方式",
            options=["综合排序", "最新排序", "最热排序"],
            value="最热排序"
        ),
        BoolInput(
            name="get_user_details",
            display_name="获取用户详情",
            info="是否获取用户的详细信息",
            value=True
        ),
        BoolInput(
            name="fetch_note_detail",
            display_name="获取完整正文",
            info="是否批量拉取笔记详情",
            value=False
        ),
        DropdownInput(
            name="note_type",
            display_name="笔记类型",
            options=["全部", "视频", "图文"],
            value="全部",
            info="选择要搜索的笔记类型"
        )
    ]

    outputs = [
        Output(display_name="爬取结果", name="result", method="build_output")
    ]

    def _emit_log(self, message: Any) -> None:
        if not hasattr(self, "_debug_logs"):
            self._debug_logs = []
        try:
            self.log(message)
        except Exception:
            pass
        self._debug_logs.append(str(message))

    def get_sort_value(self, sort_type: str) -> int:
        """将中文排序选项转换为API需要的数值"""
        sort_map = {
            "综合排序": 0,
            "最新排序": 1, 
            "最热排序": 2
        }
        return sort_map.get(sort_type, 2)

    def get_note_type_value(self, note_type: str) -> int:
        """将中文笔记类型选项转换为API需要的数值"""
        note_type_map = {
            "全部": 0,
            "图文": 1,
            "视频": 2
        }
        return note_type_map.get(note_type, 0)

    def create_payload_for_page(self, page: int, keyword: str, sort_type: int, note_type: int, bydev: int) -> Dict[str, Any]:
        pdict = {
            "keyword": keyword,
            "sort": sort_type,
            "bydev": bydev,
            "note_type": note_type,
            "page": page,
        }
        self._emit_log(f"🔧 创建Payload参数: note_type={note_type} (0=全部, 1=图文, 2=视频)")
        try:
            from urllib.parse import quote_plus
            param_str = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in pdict.items() if v is not None])
        except Exception:
            param_str = '&'.join([f"{k}={v}" for k, v in pdict.items() if v is not None])
        payload = {
            "access_token": "0d46c0462a6411edb5c200163e0627711146a2663c64d0",
            "param": param_str,
            "router": "/xhs/search",
        }
        self._emit_log(f"🔧 创建Payload: {payload}")
        return payload

    def send_request(self, payload: dict, url: str = "http://api.batmkey.cn:8000/api/v3", timeout: int = 15) -> Tuple[int, str, Dict]:
        """发送API请求"""
        self._emit_log(f"📡 发送请求到: {url}")
        self._emit_log(f"📡 请求Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        try:
            headers = {"Content-Type": "application/json"}
            
            # 创建请求
            def _do_req(body: dict):
                data_bytes = json.dumps(body).encode('utf-8')
                req = request.Request(url, data=data_bytes, headers=headers)
                return req, data_bytes
            req, req_data = _do_req(payload)
            
            self._emit_log(f"📡 请求头: {headers}")
            self._emit_log(f"📡 请求数据大小: {len(req_data)} bytes")
            
            # 发送请求
            with request.urlopen(req, timeout=timeout) as response:
                status = response.getcode()
                body = response.read()
                
                self._emit_log(f"📡 响应状态码: {status}")
                self._emit_log(f"📡 响应数据大小: {len(body)} bytes")
                self._emit_log(f"📡 响应前100字符: {body[:100].decode('utf-8', errors='ignore')}")
                
                try:
                    response_data = json.loads(body.decode('utf-8'))
                    self._emit_log(f"📡 JSON解析成功，数据类型: {type(response_data)}")
                    if isinstance(response_data, dict):
                        self._emit_log(f"📡 响应数据键: {list(response_data.keys())}")
                        if 'data' in response_data:
                            self._emit_log(f"📡 data字段类型: {type(response_data['data'])}")
                            if isinstance(response_data['data'], dict):
                                self._emit_log(f"📡 data字典键: {list(response_data['data'].keys())}")
                                if 'items' in response_data['data']:
                                    items = response_data['data']['items']
                                    self._emit_log(f"📡 items字段类型: {type(items)}")
                                    if isinstance(items, list):
                                        self._emit_log(f"📡 items数组长度: {len(items)}")
                        else:
                            if isinstance(payload.get('param'), dict):
                                try:
                                    from urllib.parse import quote_plus
                                    pdict = payload['param']
                                    pstr = '&'.join([f"{k}={quote_plus(str(v))}" for k, v in pdict.items() if v is not None])
                                    fallback = dict(payload)
                                    fallback['param'] = pstr
                                    self._emit_log(f"🔄 回退为字符串param: {fallback['param']}")
                                    req_fb, req_fb_data = _do_req(fallback)
                                    self._emit_log(f"📡 回退请求数据大小: {len(req_fb_data)} bytes")
                                    with request.urlopen(req_fb, timeout=timeout) as resp2:
                                        st2 = resp2.getcode()
                                        bd2 = resp2.read()
                                        self._emit_log(f"📡 回退响应状态码: {st2}")
                                        try:
                                            rd2 = json.loads(bd2.decode('utf-8'))
                                            self._emit_log(f"📡 回退解析成功，键: {list(rd2.keys()) if isinstance(rd2, dict) else 'Not dict'}")
                                            return st2, "OK", rd2 if isinstance(rd2, dict) else {}
                                        except Exception as e:
                                            self._emit_log(f"❌ 回退解析错误: {e}")
                                            return st2, f"回退解析错误: {e}", {}
                                except Exception as e:
                                    self._emit_log(f"❌ 回退构造错误: {e}")
                                    return status, "OK", response_data
                    return status, "OK", response_data
                except json.JSONDecodeError as e:
                    self._emit_log(f"❌ JSON解析错误: {e}")
                    self._emit_log(f"❌ 原始响应: {body.decode('utf-8', errors='ignore')}")
                    return status, f"JSON解析错误: {e}", {}
                    
        except error.HTTPError as e:
            self._emit_log(f"❌ HTTP错误: {e.code} - {e}")
            return e.code, str(e), {}
        except error.URLError as e:
            self._emit_log(f"❌ URL错误: {e}")
            return 0, f"网络错误: {e}", {}
        except Exception as e:
            self._emit_log(f"❌ 请求异常: {e}")
            return 0, f"请求异常: {e}", {}

    def decode_unicode_text(self, text: str) -> str:
        """解码Unicode转义字符和UTF-8编码"""
        if not text:
            return ""
        try:
            # 首先尝试处理 \uXXXX 格式的Unicode转义
            try:
                decoded = text.encode().decode('unicode_escape')
                # 如果解码后仍然是乱码，尝试UTF-8解码
                if any(ord(c) > 127 for c in decoded):
                    try:
                        # 将字符串编码为latin-1，然后解码为UTF-8
                        utf8_decoded = decoded.encode('latin-1').decode('utf-8')
                        return utf8_decoded
                    except:
                        pass
                return decoded
            except:
                # 如果Unicode转义失败，直接尝试UTF-8解码
                try:
                    # 将字符串编码为latin-1，然后解码为UTF-8
                    utf8_decoded = text.encode('latin-1').decode('utf-8')
                    return utf8_decoded
                except:
                    return text
        except:
            return text

    def extract_note_data(self, item: Dict[str, Any], search_note_type: int = 0) -> Optional[Dict[str, Any]]:
        """从单个item中提取笔记数据
        Args:
            item: 笔记数据项
            search_note_type: 搜索的笔记类型 (0=全部, 1=图文, 2=视频)
        """
        self._emit_log(f"🔍 开始提取数据，item类型: {type(item)}, 搜索类型: {search_note_type}")
        self._emit_log(f"🔍 item键: {list(item.keys()) if isinstance(item, dict) else 'Not a dict'}")
        
        if not isinstance(item, dict):
            self._emit_log(f"❌ item不是字典类型: {type(item)}")
            return None
            
        model_type = item.get("model_type")
        self._emit_log(f"🔍 model_type: {model_type}")
        
        
        note = item["note"]
        self._emit_log(f"🔍 note类型: {type(note)}")
        self._emit_log(f"🔍 note键: {list(note.keys()) if isinstance(note, dict) else 'Not a dict'}")
        
        note_type = note.get("type")
        self._emit_log(f"🔍 笔记类型: {note_type}")
        
        # 允许所有类型，后续统一映射为中文类别
        
        user = note.get("user", {})
        self._emit_log(f"🔍 用户信息类型: {type(user)}")
        self._emit_log(f"🔍 用户信息键: {list(user.keys()) if isinstance(user, dict) else 'Not a dict'}")
        
        # 获取原始文本并进行调试
        raw_title = note.get("title", "")
        raw_desc = note.get("desc", "")
        self._emit_log(f"🔍 原始标题: {repr(raw_title)}")
        self._emit_log(f"🔍 原始描述: {repr(raw_desc)}")
        
        # 提取基本信息
        nt = note.get("type", "")
        vobj_tmp = note.get("video") or note.get("video_info") or note.get("video_info_v2")
        is_video_note = (nt == "video") or isinstance(vobj_tmp, dict)
        nt_cn = "视频笔记" if is_video_note else ("图文笔记" if nt == "normal" else "其他")
        extracted = {
            "笔记ID": note.get("id", ""),
            "标题": self.decode_unicode_text(raw_title),
            "笔记正文": self.decode_unicode_text(raw_desc),
            "笔记类型": nt_cn,
            "点赞数": note.get("liked_count", 0),
            "收藏数": note.get("collected_count", 0),
            "评论数": note.get("comments_count", 0),
            "分享数": note.get("shared_count", note.get("share_count", note.get("forward_count", 0))),
            "作者昵称": self.decode_unicode_text(user.get("nickname", "")),
            "作者ID": user.get("userid", ""),
            "小红书号": user.get("red_id", ""),
        
            "是否官方认证": bool(user.get("red_official_verified", False)),
        }
        
        self._emit_log(f"🔍 解码后标题: {extracted['标题']}")
        self._emit_log(f"🔍 解码后描述: {extracted['笔记正文']}")
        self._emit_log(f"✅ 基本信息提取完成: {extracted['笔记ID']} - {extracted['标题']}")
        
        ts = note.get("timestamp") or note.get("update_time")
        pub_text = ""
        try:
            if isinstance(ts, int) and ts > 0:
                if ts > 10**12:
                    dt = datetime.fromtimestamp(ts / 1000)
                elif ts > 10**9:
                    dt = datetime.fromtimestamp(ts)
                else:
                    dt = None
                extracted["发布时间"] = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""
            else:
                cti = note.get("corner_tag_info")
                if isinstance(cti, list):
                    for it in cti:
                        if isinstance(it, dict) and it.get("type") == "publish_time":
                            pub_text = it.get("text") or ""
                            break
                extracted["发布时间"] = pub_text
        except Exception:
            extracted["发布时间"] = ""
        
        # 处理图片列表
        images_list = note.get("images_list", [])
        self._emit_log(f"🔍 图片列表类型: {type(images_list)}, 长度: {len(images_list) if isinstance(images_list, list) else 'Not a list'}")
        
        cover_url = ""
        image_urls = []
        video_urls = []
        video_ids = []
        
        # 处理图片列表（如果有）
        if isinstance(images_list, list) and len(images_list) > 0:
            for i, img in enumerate(images_list):
                self._emit_log(f"🔍 图片{i+1}类型: {type(img)}")
                if isinstance(img, dict):
                    self._emit_log(f"🔍 图片{i+1}键: {list(img.keys())}")
                    url = (
                        img.get("url")
                        or img.get("url_size_large")
                        or img.get("url_size_medium")
                        or img.get("url_size_small")
                        or img.get("original")
                    )
                    if url:
                        image_urls.append(url)
                        if not cover_url:
                            cover_url = url
                    live_photo = img.get("live_photo")
                    if isinstance(live_photo, dict):
                        media = live_photo.get("media", {})
                        vid = media.get("video_id")
                        if vid is not None:
                            video_ids.append(vid)
                        streams = media.get("streams")
                        if isinstance(streams, list):
                            for s in streams:
                                mu = s.get("master_url")
                                if mu:
                                    video_urls.append(mu)
                                burls = s.get("backup_urls")
                                if isinstance(burls, list):
                                    for bu in burls:
                                        if isinstance(bu, str):
                                            video_urls.append(bu)
                        else:
                            stream = media.get("stream", {})
                            if isinstance(stream, dict):
                                for k in ["h265", "h264", "av1", "h266"]:
                                    arr = stream.get(k)
                                    if isinstance(arr, list):
                                        for s in arr:
                                            mu = s.get("master_url")
                                            if mu:
                                                video_urls.append(mu)
                                            burls = s.get("backup_urls")
                                            if isinstance(burls, list):
                                                for bu in burls:
                                                    if isinstance(bu, str):
                                                        video_urls.append(bu)
                elif isinstance(img, str):
                    image_urls.append(img)
                    if not cover_url:
                        cover_url = img
        
        # 处理视频信息（无论images_list是否为空，都要检查视频字段）
        # 这对于视频笔记特别重要，因为视频笔记的images_list可能为空
        self._emit_log(f"🔍 开始提取视频信息，笔记类型: {note.get('type')}, 搜索类型: {search_note_type}")
        
        # 根据搜索类型决定视频URL提取方式
        if search_note_type == 2:
            # 视频笔记搜索：使用简化URL格式，从 widgets_context 中提取 origin_video_key
            video_key = None
            widgets_context = note.get("widgets_context", "")
            if widgets_context:
                try:
                    import json
                    widgets_data = json.loads(widgets_context)
                    if isinstance(widgets_data, dict):
                        video_key = widgets_data.get("origin_video_key")
                        self._emit_log(f"🔍 从widgets_context提取到origin_video_key: {video_key}")
                except Exception as e:
                    self._emit_log(f"⚠️ 解析widgets_context失败: {e}")
            
            if video_key:
                simplified_url = f"https://sns-video-hs.xhscdn.com/{video_key}"
                video_urls.append(simplified_url)
                self._emit_log(f"🔍 视频笔记搜索模式：使用简化URL: {simplified_url}")
            else:
                self._emit_log(f"⚠️ 未找到origin_video_key，笔记ID: {note.get('id', '')}")
        elif search_note_type == 0:
            # 混合搜索：优先从 video_info_v2 中提取详细视频链接，如果失败则尝试从 widgets_context 提取
            # 先尝试从 widgets_context 提取（作为备用方案）
            video_key = None
            widgets_context = note.get("widgets_context", "")
            if widgets_context:
                try:
                    import json
                    widgets_data = json.loads(widgets_context)
                    if isinstance(widgets_data, dict):
                        video_key = widgets_data.get("origin_video_key")
                        if video_key:
                            self._emit_log(f"🔍 混合搜索模式：从widgets_context提取到origin_video_key: {video_key}")
                except Exception as e:
                    self._emit_log(f"⚠️ 解析widgets_context失败: {e}")
            
            if video_key:
                simplified_url = f"https://sns-video-hs.xhscdn.com/{video_key}"
                video_urls.append(simplified_url)
                self._emit_log(f"🔍 混合搜索模式：使用简化URL: {simplified_url}")
            
            # 继续从 video_info_v2 中提取详细视频链接（如果还没有提取到）
            if not video_urls:
                # 混合搜索：从 video_info_v2 中提取详细视频链接
                # 优先处理 video_info_v2（这是视频笔记的主要结构）
                vobj2 = note.get("video_info_v2")
            if isinstance(vobj2, dict):
                self._emit_log(f"🔍 找到video_info_v2对象，键: {list(vobj2.keys())}")
                media = vobj2.get("media")
                if isinstance(media, dict):
                    self._emit_log(f"🔍 找到media对象，键: {list(media.keys())}")
                    # 处理 media.stream 结构（h264, h265等）
                    stream2 = media.get("stream")
                    if isinstance(stream2, dict):
                        self._emit_log(f"🔍 找到stream对象，键: {list(stream2.keys())}")
                        for k in ["h265", "h264", "av1", "h266"]:
                            arr = stream2.get(k)
                            if isinstance(arr, list) and len(arr) > 0:
                                self._emit_log(f"🔍 找到{k}数组，长度: {len(arr)}")
                                for idx, s in enumerate(arr):
                                    if isinstance(s, dict):
                                        mu = s.get("master_url") or s.get("url")
                                        if mu:
                                            video_urls.append(mu)
                                            self._emit_log(f"🔍 从{k}[{idx}]提取到视频链接: {mu[:80]}...")
                                        burls = s.get("backup_urls")
                                        if isinstance(burls, list):
                                            for bu in burls:
                                                if isinstance(bu, str) and bu:
                                                    video_urls.append(bu)
                                                    self._emit_log(f"🔍 从{k}[{idx}]提取到备用链接: {bu[:80]}...")
                    # 也检查 media.streams（如果存在）
                    streams2 = media.get("streams")
                    if isinstance(streams2, list) and len(streams2) > 0:
                        self._emit_log(f"🔍 找到streams数组，长度: {len(streams2)}")
                        for idx, s in enumerate(streams2):
                            if isinstance(s, dict):
                                mu = s.get("master_url") or s.get("url")
                                if mu:
                                    video_urls.append(mu)
                                    self._emit_log(f"🔍 从streams[{idx}]提取到视频链接: {mu[:80]}...")
                                burls = s.get("backup_urls")
                                if isinstance(burls, list):
                                    for bu in burls:
                                        if isinstance(bu, str) and bu:
                                            video_urls.append(bu)
            
            # 处理 video 或 video_info（旧版结构）
            vobj = note.get("video") or note.get("video_info")
            if isinstance(vobj, dict):
                self._emit_log(f"🔍 找到video/video_info对象，键: {list(vobj.keys())}")
                streams = vobj.get("streams")
                if isinstance(streams, list):
                    for s in streams:
                        mu = s.get("master_url") or s.get("url")
                        if mu:
                            video_urls.append(mu)
                        burls = s.get("backup_urls")
                        if isinstance(burls, list):
                            for bu in burls:
                                if isinstance(bu, str):
                                    video_urls.append(bu)
                else:
                    stream = vobj.get("stream")
                    if isinstance(stream, dict):
                        for k in ["h265", "h264", "av1", "h266"]:
                            arr = stream.get(k)
                            if isinstance(arr, list):
                                for s in arr:
                                    mu = s.get("master_url") or s.get("url")
                                    if mu:
                                        video_urls.append(mu)
                                    burls = s.get("backup_urls")
                                    if isinstance(burls, list):
                                        for bu in burls:
                                            if isinstance(bu, str):
                                                video_urls.append(bu)
                direct_keys = ["url", "play_url", "main_url", "video_url", "hls_video_url", "hls_url"]
                for dk in direct_keys:
                    dv = vobj.get(dk)
                    if isinstance(dv, str) and dv:
                        video_urls.append(dv)
        # search_note_type == 1 (图文笔记) 不需要提取视频URL
        
        # 去重并设置结果
        image_urls = list(dict.fromkeys([u for u in image_urls if u]))
        video_urls = list(dict.fromkeys([u for u in video_urls if u]))
        video_ids = list(dict.fromkeys(video_ids))
        extracted["封面图链接"] = ([cover_url] if cover_url else [])
        extracted["视频链接"] = video_urls
        
        # 为图文笔记添加所有图片URL列表和图片数量
        # 判断是否为图文笔记：笔记类型为"图文笔记"
        note_type_str = extracted.get("笔记类型", "")
        is_image_note = (note_type_str == "图文笔记")
        if is_image_note:
            extracted["所有图片链接"] = image_urls
            extracted["图片数量"] = len(image_urls)
            self._emit_log(f"✅ 图文笔记：共{len(image_urls)}张图片")
        else:
            # 对于非图文笔记（视频笔记等），不输出所有图片链接
            extracted["所有图片链接"] = []
            extracted["图片数量"] = 0
        
        self._emit_log(f"✅ 图片处理完成，共{len(image_urls)}张")
        self._emit_log(f"✅ 视频处理完成，共{len(video_urls)}条")
        extracted["好看数"] = note.get("nice_count", 0)
        nid = extracted.get("笔记ID") or ""
        extracted["笔记链接"] = f"https://www.xiaohongshu.com/explore/{nid}" if nid else ""
        try:
            txt = (extracted.get("笔记正文") or "") + " " + (extracted.get("标题") or "")
            txt = txt.replace("＃", "#")
            tags = re.findall(r"(?:^|\s)#([\w\-\u4e00-\u9fa5]+)", txt)
            tags = [t.strip() for t in tags if t]
            tags = list(dict.fromkeys(tags))
            extracted["笔记tag"] = "; ".join(tags) if tags else ""
        except Exception:
            extracted["笔记tag"] = ""
        return extracted

    def fetch_data(self, keyword: str, start_page: int, end_page: int, sort_type: int, note_type: int) -> List[Dict[str, Any]]:
        """获取数据"""
        self._emit_log(f"🚀 开始获取数据")
        self._emit_log(f"🚀 参数 - 关键词: {keyword}, 页数: {start_page}-{end_page}, 排序: {sort_type}, 笔记类型: {note_type}")
        
        all_data = []
        bydev = 1
        
        for page in range(start_page, end_page + 1):
            self._emit_log(f"\n📄 处理第 {page} 页，bydev: {bydev}")
            
            # 创建payload
            payload = self.create_payload_for_page(page, keyword, sort_type, note_type, bydev)
            
            # 发送请求
            status, reason, response_data = self.send_request(payload)
            
            # 业务状态检查 - 即使HTTP成功也要检查API业务状态
            if 200 <= status < 300 and response_data:
                # 检查API业务状态码 - 兼容两种字段名
                api_code = response_data.get("code") or response_data.get("status_code")
                
                # 检查响应结构是否包含data字段
                has_data_field = "data" in response_data and isinstance(response_data["data"], dict)
                
                # 成功条件：状态码为200且有data字段
                if api_code == 200 and has_data_field:
                    all_data.append(response_data)
                    self._emit_log(f"✅ 第 {page} 页数据获取成功 (业务码: {api_code})")
                else:
                    # API业务错误，记录详细信息但仍然添加到结果列表
                    error_msg = response_data.get("message") or response_data.get("msg", "未知错误")
                    self._emit_log(f"⚠️ 第 {page} 页API业务错误: {error_msg} (业务码: {api_code})")
                    self._emit_log(f"⚠️ 响应结构: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
                    
                    # 保存错误响应到结果列表，以便在build_output中检测和处理
                    all_data.append(response_data)
                    
                    # 在日志中记录完整响应以便调试
                    self._emit_log(f"⚠️ 完整响应: {json.dumps(response_data, ensure_ascii=False)}")
            else:
                # HTTP错误
                self._emit_log(f"❌ 第 {page} 页请求失败: {status} {reason}")
                # 保存错误信息，便于后续批量处理
                all_data.append({
                    "error": {
                        "http_status": status,
                        "reason": reason,
                        "page": page
                    }
                })
            
            # 页面间延迟
            if page < end_page:
                self._emit_log(f"⏱️ 等待1秒...")
                time.sleep(1)
            
            bydev += 1
        
        self._emit_log(f"🚀 数据获取完成，共处理 {len(all_data)} 页数据")
        return all_data

    def extract_all_data(self, response_data_list: List[Dict[str, Any]], note_type: int = 0) -> List[Dict[str, Any]]:
        """从所有响应数据中提取笔记数据
        Args:
            response_data_list: 响应数据列表
            note_type: 搜索的笔记类型 (0=全部, 1=图文, 2=视频)
        """
        self._emit_log(f"🔄 开始提取所有数据，共 {len(response_data_list)} 页，搜索类型: {note_type}")
        
        all_extracted_data = []
        
        for page_idx, response_data in enumerate(response_data_list, 1):
            self._emit_log(f"\n📄 处理第 {page_idx} 页数据...")
            self._emit_log(f"📄 响应数据类型: {type(response_data)}")
            
            # 检查是否为错误响应
            if "error" in response_data:
                error_info = response_data["error"]
                self._emit_log(f"⚠️ 第 {page_idx} 页包含错误信息: HTTP {error_info.get('http_status', '未知')} - {error_info.get('reason', '未知原因')}")
                # 跳过错误页面的数据处理
                continue
            
            # 检查响应数据结构
            if not isinstance(response_data, dict):
                self._emit_log(f"❌ 第 {page_idx} 页数据格式错误，不是字典类型")
                continue
            
            self._emit_log(f"📄 响应数据键: {list(response_data.keys())}")
            
            # 获取data字段
            data_field = response_data.get("data", {})
            self._emit_log(f"📄 data字段类型: {type(data_field)}")
            
            if not isinstance(data_field, dict):
                self._emit_log(f"❌ 第 {page_idx} 页data字段不是字典类型: {type(data_field)}")
                continue
            
            self._emit_log(f"📄 data字典键: {list(data_field.keys())}")
            
            # 获取items列表 - 这是关键修正！
            items_list = data_field.get("items", [])
            self._emit_log(f"📄 items字段类型: {type(items_list)}")
            
            if not items_list:
                self._emit_log(f"❌ 第 {page_idx} 页没有items字段或items为空")
                # 打印完整的data字段以便调试
                self._emit_log(f"📄 完整data字段: {json.dumps(data_field, ensure_ascii=False, indent=2)}")
                continue
            
            if not isinstance(items_list, list):
                self._emit_log(f"❌ 第 {page_idx} 页items字段不是列表类型: {type(items_list)}")
                continue
                
            self._emit_log(f"📄 items列表长度: {len(items_list)}")
            
            # 提取每个笔记的数据
            for item_idx, item in enumerate(items_list):
                self._emit_log(f"\n🔍 处理第 {page_idx} 页第 {item_idx + 1} 条数据")
                try:
                    extracted_data = self.extract_note_data(item, note_type)
                    if extracted_data:
                        all_extracted_data.append(extracted_data)
                        self._emit_log(f"✅ 第 {page_idx} 页第 {item_idx + 1} 条数据提取成功")
                    else:
                        self._emit_log(f"⚠️ 第 {page_idx} 页第 {item_idx + 1} 条数据跳过")
                except Exception as e:
                    self._emit_log(f"❌ 第 {page_idx} 页第 {item_idx + 1} 条数据提取失败: {e}")
                    import traceback
                    self._emit_log(f"❌ 错误详情: {traceback.format_exc()}")
        
        self._emit_log(f"🔄 数据提取完成，共提取 {len(all_extracted_data)} 条有效数据")
        return all_extracted_data

    def create_user_profile_payload(self, userid: str) -> Dict[str, Any]:
        payload = {
            "access_token": "0d46c0462a6411edb5c200163e0627711146a2663c64d0",
            "param": {
                "user_id": userid,
            },
            "router": "/xhs/user/info",
        }
        return payload

    def create_note_detail_payload(self, note_id: str) -> Dict[str, Any]:
        try:
            from urllib.parse import quote_plus
            p = f"note_id={quote_plus(str(note_id))}"
        except Exception:
            p = f"note_id={note_id}"
        payload = {
            "access_token": "0d46c0462a6411edb5c200163e0627711146a2663c64d0",
            "param": p,
            "router": "/xhs/note/detail",
        }
        return payload

    def parse_note_detail_data(self, detail: Dict[str, Any], note_id: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        data_field = detail.get("data")
        target_note = None
        if isinstance(data_field, list):
            for block in data_field:
                if isinstance(block, dict):
                    nl = block.get("note_list")
                    if isinstance(nl, list):
                        for n in nl:
                            if isinstance(n, dict):
                                if str(n.get("id")) == str(note_id):
                                    target_note = n
                                    break
                        if target_note:
                            break
        elif isinstance(data_field, dict):
            nl = data_field.get("note_list")
            if isinstance(nl, list) and nl:
                target_note = nl[0]
        if isinstance(target_note, dict):
            desc = target_note.get("desc") or ""
            ip = target_note.get("ip_location") or ""
            tags = []
            ht = target_note.get("hash_tag")
            if isinstance(ht, list):
                for t in ht:
                    if isinstance(t, dict):
                        nm = t.get("name")
                        if nm:
                            tags.append(str(nm))
            result["笔记完整正文"] = self.decode_unicode_text(desc)
            result["笔记关联话题"] = "; ".join(list(dict.fromkeys(tags))) if tags else ""
            result["作者IP"] = ip
        return result

    def fetch_note_details_for_ids(self, note_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        details_map: Dict[str, Dict[str, Any]] = {}
        unique_ids = []
        seen = set()
        for nid in note_ids:
            if nid and nid not in seen:
                seen.add(nid)
                unique_ids.append(nid)
        for nid in unique_ids:
            try:
                payload = self.create_note_detail_payload(nid)
                status, reason, resp = self.send_request(payload)
                if 200 <= status < 300 and isinstance(resp, dict):
                    parsed = self.parse_note_detail_data(resp, nid)
                    if parsed:
                        details_map[nid] = parsed
                else:
                    pass
            except Exception:
                pass
        return details_map

    def augment_notes_with_note_details(self, notes: List[Dict[str, Any]], details_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        for item in notes:
            nid = item.get("笔记id") or item.get("笔记ID")
            if nid and nid in details_map:
                item.update(details_map[nid])
                dt_tags = details_map[nid].get("笔记关联话题")
                if isinstance(dt_tags, str) and dt_tags:
                    item["笔记tag"] = dt_tags
        return notes

    def parse_user_profile_data(self, user_data: Dict[str, Any], userid: str) -> Dict[str, Any]:
        data = user_data or {}
        fans = data.get("fans")
        interactions = data.get("interactions")
        if fans is None and isinstance(interactions, list):
            for it in interactions:
                if isinstance(it, dict) and it.get("type") == "fans":
                    fans = it.get("count")
                    break
        liked = data.get("liked")
        collected = data.get("collected")
        likes_collects = None
        if isinstance(interactions, list):
            for it in interactions:
                if isinstance(it, dict) and it.get("type") == "interaction":
                    likes_collects = it.get("count")
                    break
        if likes_collects is None:
            if isinstance(liked, int) and isinstance(collected, int):
                likes_collects = liked + collected
            else:
                ns = data.get("note_num_stat", {})
                lk = ns.get("liked")
                cl = ns.get("collected")
                if isinstance(lk, int) and isinstance(cl, int):
                    likes_collects = lk + cl
        # 尝试多种方式获取用户简介
        desc = ""
        # 方式1: user_desc_info.desc
        user_desc_info = data.get("user_desc_info", {})
        if isinstance(user_desc_info, dict):
            desc = user_desc_info.get("desc") or ""
        # 方式2: 直接获取desc字段
        if not desc:
            desc = data.get("desc") or ""
        # 方式3: share_info.content
        if not desc:
            share_info = data.get("share_info", {})
            if isinstance(share_info, dict):
                desc = share_info.get("content") or ""
        # 确保是字符串类型
        desc = str(desc) if desc else ""
        share_link = data.get("share_link")
        if not share_link:
            share_link = f"https://www.xiaohongshu.com/user/profile/{userid}" if userid else ""
        result = {
            "作者粉丝数": fans or 0,
            "作者获赞与收藏数": likes_collects or 0,
            "作者简介": desc,
            "作者主页链接": share_link,
        }
        return result

    def fetch_user_details_for_ids(self, user_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        details_map: Dict[str, Dict[str, Any]] = {}
        unique_ids = []
        seen = set()
        for uid in user_ids:
            if uid and uid not in seen:
                seen.add(uid)
                unique_ids.append(uid)
        for uid in unique_ids:
            try:
                payload = self.create_user_profile_payload(uid)
                status, reason, resp = self.send_request(payload)
                if 200 <= status < 300 and isinstance(resp, dict):
                    data_field = resp.get("data")
                    target = data_field if isinstance(data_field, dict) else resp
                    if isinstance(target, dict):
                        parsed = self.parse_user_profile_data(target, uid)
                        if parsed:
                            details_map[uid] = parsed
                        else:
                            self._emit_log(f"⚠️ 用户详情解析为空: {uid}")
                    else:
                        self._emit_log(f"⚠️ 用户详情数据格式错误: {uid}")
                else:
                    self._emit_log(f"⚠️ 用户详情HTTP失败: {uid} {status} {reason}")
            except Exception as e:
                self._emit_log(f"❌ 获取用户详情异常: {uid} {e}")
        return details_map

    def augment_notes_with_user_details(self, notes: List[Dict[str, Any]], details_map: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        for item in notes:
            uid = item.get("作者ID")
            if uid and uid in details_map:
                item.update(details_map[uid])
        return notes

    def build_output(self) -> Data:
        """
        LangFlow调用该组件时执行的核心方法
        """
        self._debug_logs = []
        self.status = "开始执行小红书爬虫组件"
        self._emit_log("🎯 开始执行小红书爬虫组件")
        
        try:
            # 获取输入参数
            keyword = self.keyword
            start_page = self.start_page
            end_page = self.end_page
            sort_type_str = self.sort_type
            note_type_str = self.note_type
            get_user_details = self.get_user_details
            fetch_note_detail = self.fetch_note_detail
            # download_images = self.download_images
            # image_max_width = self.image_max_width
            # image_max_height = self.image_max_height
            
            # 验证页数范围
            if start_page > end_page:
                error_msg = f"输入参数不合格: 开始页数({start_page})不能大于结束页数({end_page})"
                self._emit_log(f"❌ {error_msg}")
                return Data(value={
                    "status": "error",
                    "message": error_msg,
                    "total_items": 0,
                    "logs": self._debug_logs
                })
            
            # 精简日志输出，详细日志只在工作流日志面板显示
            self.log("🎯 输入参数:")
            self.log(f"   关键词: {keyword}")
            self.log(f"   页数范围: {start_page} - {end_page}")
            self.log(f"   排序方式: {sort_type_str}")
            self.log(f"   笔记类型: {note_type_str}")
            self.log(f"   获取用户详情: {get_user_details}")
            
            # 转换排序类型和笔记类型
            sort_type = self.get_sort_value(sort_type_str)
            note_type = self.get_note_type_value(note_type_str)
            self.log(f"🎯 排序类型转换: {sort_type_str} -> {sort_type}")
            self.log(f"🎯 笔记类型转换: {note_type_str} -> {note_type}")
            
            # 获取数据
            response_data_list = self.fetch_data(keyword, start_page, end_page, sort_type, note_type)
            
            # 检查是否有API错误响应
            api_errors = []
            for resp in response_data_list:
                if isinstance(resp, dict) and ("msg" in resp or "message" in resp) and ("status_code" in resp or "code" in resp):
                    # 这是一个API错误响应
                    error_msg = resp.get("msg") or resp.get("message", "未知错误")
                    error_code = resp.get("status_code") or resp.get("code", 0)
                    api_errors.append({
                        "msg": error_msg,
                        "status_code": error_code
                    })
                    self._emit_log(f"❌ API错误: {error_msg} (状态码: {error_code})")
            
            # 如果所有响应都是错误，直接返回错误信息
            if len(api_errors) == len(response_data_list) and api_errors:
                # 如果所有页面都返回错误，返回第一个错误信息
                first_error = api_errors[0]
                return Data(value={
                    "status": "error",
                    "message": f"API请求失败: {first_error['msg']}",
                    "total_items": 0,
                    "error_info": first_error,
                    "all_errors": api_errors
                })
            
            if not response_data_list:
                error_msg = "没有获取到任何响应数据"
                self.log(f"❌ {error_msg}")
                return Data(value={
                    "status": "no_data",
                    "message": error_msg,
                    "total_items": 0,
                    "debug_info": "API请求失败，没有返回任何数据"
                    # 移除logs字段，日志只在工作流日志面板显示
                })
            
            # 提取数据
            extracted_data = self.extract_all_data(response_data_list, note_type)
            
            if not extracted_data:
                error_msg = "没有提取到有效数据"
                self.log(f"❌ {error_msg}")
                
                # 提供详细的调试信息
                debug_info = {
                    "response_count": len(response_data_list),
                    "response_samples": [],
                    "api_errors": api_errors  # 添加API错误信息
                }
                
                for i, resp in enumerate(response_data_list[:2]):  # 只显示前2个响应的样本
                    sample_info = {
                        "page": i + 1,
                        "type": str(type(resp)),
                        "keys": list(resp.keys()) if isinstance(resp, dict) else "Not a dict"
                    }
                    
                    if isinstance(resp, dict) and "data" in resp:
                        data_field = resp["data"]
                        sample_info["data_type"] = str(type(data_field))
                        if isinstance(data_field, dict):
                            sample_info["data_keys"] = list(data_field.keys())
                            if "items" in data_field:
                                items = data_field["items"]
                                sample_info["items_type"] = str(type(items))
                                sample_info["items_length"] = len(items) if isinstance(items, list) else "Not a list"
                    
                    debug_info["response_samples"].append(sample_info)
                
                # 如果有API错误，在调试信息中包含第一个错误
                if api_errors:
                    return Data(value={
                        "status": "error", 
                        "message": f"API请求失败: {api_errors[0]['msg']}",
                        "total_items": 0,
                        "error_info": api_errors[0],
                        "debug_info": debug_info
                        # 移除logs字段，日志只在工作流日志面板显示
                    })
                else:
                    return Data(value={
                        "status": "no_data", 
                        "message": error_msg,
                        "total_items": 0,
                        "debug_info": debug_info
                        # 移除logs字段，日志只在工作流日志面板显示
                    })
            
            # 如果有部分API错误，在结果中包含错误信息
            if api_errors:
                self._emit_log(f"⚠️ 共有 {len(api_errors)} 个API错误，但仍有部分数据成功提取")
            
            if get_user_details:
                try:
                    user_ids = [d.get("作者ID") for d in extracted_data]
                    details_map = self.fetch_user_details_for_ids(user_ids)
                    extracted_data = self.augment_notes_with_user_details(extracted_data, details_map)
                except Exception as e:
                    self._emit_log(f"⚠️ 合并用户详情失败: {e}")
            if fetch_note_detail:
                try:
                    note_ids = [d.get("笔记ID") or d.get("笔记id") for d in extracted_data]
                    note_ids = [nid for nid in note_ids if nid]
                    nd_map = self.fetch_note_details_for_ids(note_ids)
                    extracted_data = self.augment_notes_with_note_details(extracted_data, nd_map)
                except Exception as e:
                    self._emit_log(f"⚠️ 合并笔记详情失败: {e}")
            field_order = [
                # 搜索结果字段
                "笔记id","标题","笔记类型","发布时间","笔记链接",
                "封面图链接","视频链接","所有图片链接","图片数量","笔记正文","笔记tag",
                "点赞数","评论数","收藏数","好看数","分享数",
                # 用户详情字段
                "作者ID","作者昵称","小红书号","是否官方认证",
                "作者粉丝数","作者获赞与收藏数","作者简介","作者主页链接",
                # 笔记详情字段
                "笔记完整正文","笔记关联话题","作者IP",
            ]
            pruned = []
            for d in extracted_data:
                d["笔记id"] = d.get("笔记ID")
                # 设置默认值
                for k, v in {
                    "作者粉丝数": 0, 
                    "作者获赞与收藏数": 0, 
                    "作者简介": "", 
                    "作者主页链接": "",
                    "所有图片链接": [],
                    "图片数量": 0
                }.items():
                    if d.get(k) is None:
                        d[k] = v
                out = {}
                for k in field_order:
                    out[k] = d.get(k)
                pruned.append(out)
            extracted_data = pruned
            # 构建结果 - 精简输出，移除详细日志
            result = {
                "status": "success",
                "message": f"成功爬取 {len(extracted_data)} 条数据",
                "total_items": len(extracted_data),
                "data": extracted_data,
                "config": {
                    "keyword": keyword,
                    "start_page": start_page,
                    "end_page": end_page,
                    "sort_type": sort_type_str,
                    "note_type": note_type_str,
                    "get_user_details": get_user_details
                    # "download_images": download_images
                }
                # 移除logs字段，日志只在工作流日志面板显示
            }
            
            self.status = f"爬取完成，共 {len(extracted_data)} 条数据"
            self.log(f"✅ 爬取完成！共获取 {len(extracted_data)} 条数据")
            
            return Data(value=result)
            
        except Exception as e:
            error_msg = f"爬取过程中发生错误: {str(e)}"
            self.log(f"❌ {error_msg}")
            import traceback
            self.log(f"❌ 错误详情: {traceback.format_exc()}")
            
            return Data(value={
                "status": "error",
                "message": error_msg,
                "total_items": 0,
                "debug_info": traceback.format_exc()
                # 移除logs字段，日志只在工作流日志面板显示
            })