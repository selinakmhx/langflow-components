#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 不可更改该文件

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
            name="download_images",
            display_name="下载图片",
            info="是否下载图片数据",
            value=False
        ),
        IntInput(
            name="image_max_width",
            display_name="图片最大宽度",
            info="下载图片的最大宽度",
            value=200
        ),
        IntInput(
            name="image_max_height",
            display_name="图片最大高度", 
            info="下载图片的最大高度",
            value=150
        )
    ]

    outputs = [
        Output(display_name="爬取结果", name="result", method="build_output")
    ]

    def get_sort_value(self, sort_type: str) -> int:
        """将中文排序选项转换为API需要的数值"""
        sort_map = {
            "综合排序": 0,
            "最新排序": 1, 
            "最热排序": 2
        }
        return sort_map.get(sort_type, 2)

    def create_payload_for_page(self, page: int, keyword: str, sort_type: int, bydev: int) -> Dict[str, Any]:
        """为指定页数创建payload"""
        payload = {
            "access_token": "0d46c0462a6411edb5c200163e0627711146a2663c64d0",
            "param": {
                "keyword": keyword,
                "sort": sort_type,
                "bydev": bydev,
                "page": page,
            },
            "router": "/xhs/search",
        }
        print(f"🔧 创建Payload: {payload}")
        return payload

    def send_request(self, payload: dict, url: str = "http://api.batmkey.cn:8000/api/v3", timeout: int = 15) -> Tuple[int, str, Dict]:
        """发送API请求"""
        print(f"📡 发送请求到: {url}")
        print(f"📡 请求Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        try:
            headers = {"Content-Type": "application/json"}
            
            # 创建请求
            req_data = json.dumps(payload).encode('utf-8')
            req = request.Request(url, data=req_data, headers=headers)
            
            print(f"📡 请求头: {headers}")
            print(f"📡 请求数据大小: {len(req_data)} bytes")
            
            # 发送请求
            with request.urlopen(req, timeout=timeout) as response:
                status = response.getcode()
                body = response.read()
                
                print(f"📡 响应状态码: {status}")
                print(f"📡 响应数据大小: {len(body)} bytes")
                print(f"📡 响应前100字符: {body[:100].decode('utf-8', errors='ignore')}")
                
                try:
                    response_data = json.loads(body.decode('utf-8'))
                    print(f"📡 JSON解析成功，数据类型: {type(response_data)}")
                    if isinstance(response_data, dict):
                        print(f"📡 响应数据键: {list(response_data.keys())}")
                        if 'data' in response_data:
                            print(f"📡 data字段类型: {type(response_data['data'])}")
                            if isinstance(response_data['data'], dict):
                                print(f"📡 data字典键: {list(response_data['data'].keys())}")
                                if 'items' in response_data['data']:
                                    items = response_data['data']['items']
                                    print(f"📡 items字段类型: {type(items)}")
                                    if isinstance(items, list):
                                        print(f"📡 items数组长度: {len(items)}")
                    return status, "OK", response_data
                except json.JSONDecodeError as e:
                    print(f"❌ JSON解析错误: {e}")
                    print(f"❌ 原始响应: {body.decode('utf-8', errors='ignore')}")
                    return status, f"JSON解析错误: {e}", {}
                    
        except error.HTTPError as e:
            print(f"❌ HTTP错误: {e.code} - {e}")
            return e.code, str(e), {}
        except error.URLError as e:
            print(f"❌ URL错误: {e}")
            return 0, f"网络错误: {e}", {}
        except Exception as e:
            print(f"❌ 请求异常: {e}")
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

    def extract_note_data(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从单个item中提取笔记数据"""
        print(f"🔍 开始提取数据，item类型: {type(item)}")
        print(f"🔍 item键: {list(item.keys()) if isinstance(item, dict) else 'Not a dict'}")
        
        if not isinstance(item, dict):
            print(f"❌ item不是字典类型: {type(item)}")
            return None
            
        model_type = item.get("model_type")
        print(f"🔍 model_type: {model_type}")
        
        if model_type != "note":
            print(f"❌ 跳过非笔记类型: {model_type}")
            return None
            
        if "note" not in item:
            print(f"❌ item中没有note字段")
            return None
        
        note = item["note"]
        print(f"🔍 note类型: {type(note)}")
        print(f"🔍 note键: {list(note.keys()) if isinstance(note, dict) else 'Not a dict'}")
        
        note_type = note.get("type")
        print(f"🔍 笔记类型: {note_type}")
        
        if note_type not in ["normal", "video"]:
            print(f"❌ 跳过不支持的笔记类型: {note_type}")
            return None
        
        user = note.get("user", {})
        print(f"🔍 用户信息类型: {type(user)}")
        print(f"🔍 用户信息键: {list(user.keys()) if isinstance(user, dict) else 'Not a dict'}")
        
        # 获取原始文本并进行调试
        raw_title = note.get("title", "")
        raw_desc = note.get("desc", "")
        print(f"🔍 原始标题: {repr(raw_title)}")
        print(f"🔍 原始描述: {repr(raw_desc)}")
        
        # 提取基本信息
        extracted = {
            "笔记ID": note.get("id", ""),
            "标题": self.decode_unicode_text(raw_title),
            "描述": self.decode_unicode_text(raw_desc),
            "笔记类型": note.get("type", ""),
            "发布时间戳": note.get("timestamp", 0),
            "点赞数": note.get("liked_count", 0),
            "收藏数": note.get("collected_count", 0),
            "评论数": note.get("comments_count", 0),
            "分享数": note.get("shared_count", note.get("share_count", note.get("forward_count", 0))),
            "作者昵称": self.decode_unicode_text(user.get("nickname", "")),
            "作者ID": user.get("userid", ""),
            "作者小红书号": user.get("red_id", ""),
            "作者头像": user.get("images", ""),
        }
        
        print(f"🔍 解码后标题: {extracted['标题']}")
        print(f"🔍 解码后描述: {extracted['描述']}")
        print(f"✅ 基本信息提取完成: {extracted['笔记ID']} - {extracted['标题']}")
        
        # 转换时间戳
        if extracted["发布时间戳"]:
            try:
                dt = datetime.fromtimestamp(extracted["发布时间戳"] / 1000)
                extracted["发布时间"] = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"⚠️ 时间戳转换失败: {e}")
                extracted["发布时间"] = ""
        else:
            extracted["发布时间"] = ""
        
        # 处理图片列表
        images_list = note.get("images_list", [])
        print(f"🔍 图片列表类型: {type(images_list)}, 长度: {len(images_list) if isinstance(images_list, list) else 'Not a list'}")
        
        if images_list:
            image_urls = []
            for i, img in enumerate(images_list):
                print(f"🔍 图片{i+1}类型: {type(img)}")
                if isinstance(img, dict):
                    print(f"🔍 图片{i+1}键: {list(img.keys())}")
                    if "url" in img:
                        image_urls.append(img["url"])
                elif isinstance(img, str):
                    image_urls.append(img)
            extracted["图片链接"] = "; ".join(image_urls)
            extracted["图片数量"] = len(image_urls)
            print(f"✅ 图片处理完成，共{len(image_urls)}张")
        else:
            extracted["图片链接"] = ""
            extracted["图片数量"] = 0
            print(f"⚠️ 没有图片数据")
        
        return extracted

    def fetch_data(self, keyword: str, start_page: int, end_page: int, sort_type: int) -> List[Dict[str, Any]]:
        """获取数据"""
        print(f"🚀 开始获取数据")
        print(f"🚀 参数 - 关键词: {keyword}, 页数: {start_page}-{end_page}, 排序: {sort_type}")
        
        all_data = []
        bydev = 1
        
        for page in range(start_page, end_page + 1):
            print(f"\n📄 处理第 {page} 页，bydev: {bydev}")
            
            # 创建payload
            payload = self.create_payload_for_page(page, keyword, sort_type, bydev)
            
            # 发送请求
            status, reason, response_data = self.send_request(payload)
            
            if 200 <= status < 300 and response_data:
                all_data.append(response_data)
                print(f"✅ 第 {page} 页数据获取成功")
            else:
                print(f"❌ 第 {page} 页请求失败: {status} {reason}")
            
            # 页面间延迟
            if page < end_page:
                print(f"⏱️ 等待1秒...")
                time.sleep(1)
            
            bydev += 1
        
        print(f"🚀 数据获取完成，共获取 {len(all_data)} 页数据")
        return all_data

    def extract_all_data(self, response_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从所有响应数据中提取笔记数据"""
        print(f"🔄 开始提取所有数据，共 {len(response_data_list)} 页")
        
        all_extracted_data = []
        
        for page_idx, response_data in enumerate(response_data_list, 1):
            print(f"\n📄 处理第 {page_idx} 页数据...")
            print(f"📄 响应数据类型: {type(response_data)}")
            
            # 检查响应数据结构
            if not isinstance(response_data, dict):
                print(f"❌ 第 {page_idx} 页数据格式错误，不是字典类型")
                continue
            
            print(f"📄 响应数据键: {list(response_data.keys())}")
            
            # 获取data字段
            data_field = response_data.get("data", {})
            print(f"📄 data字段类型: {type(data_field)}")
            
            if not isinstance(data_field, dict):
                print(f"❌ 第 {page_idx} 页data字段不是字典类型: {type(data_field)}")
                continue
            
            print(f"📄 data字典键: {list(data_field.keys())}")
            
            # 获取items列表 - 这是关键修正！
            items_list = data_field.get("items", [])
            print(f"📄 items字段类型: {type(items_list)}")
            
            if not items_list:
                print(f"❌ 第 {page_idx} 页没有items字段或items为空")
                # 打印完整的data字段以便调试
                print(f"📄 完整data字段: {json.dumps(data_field, ensure_ascii=False, indent=2)}")
                continue
            
            if not isinstance(items_list, list):
                print(f"❌ 第 {page_idx} 页items字段不是列表类型: {type(items_list)}")
                continue
                
            print(f"📄 items列表长度: {len(items_list)}")
            
            # 提取每个笔记的数据
            for item_idx, item in enumerate(items_list):
                print(f"\n🔍 处理第 {page_idx} 页第 {item_idx + 1} 条数据")
                try:
                    extracted_data = self.extract_note_data(item)
                    if extracted_data:
                        all_extracted_data.append(extracted_data)
                        print(f"✅ 第 {page_idx} 页第 {item_idx + 1} 条数据提取成功")
                    else:
                        print(f"⚠️ 第 {page_idx} 页第 {item_idx + 1} 条数据跳过")
                except Exception as e:
                    print(f"❌ 第 {page_idx} 页第 {item_idx + 1} 条数据提取失败: {e}")
                    import traceback
                    print(f"❌ 错误详情: {traceback.format_exc()}")
        
        print(f"🔄 数据提取完成，共提取 {len(all_extracted_data)} 条有效数据")
        return all_extracted_data

    def build_output(self) -> Data:
        """
        LangFlow调用该组件时执行的核心方法
        """
        print(f"🎯 开始执行小红书爬虫组件")
        
        try:
            # 获取输入参数
            keyword = self.keyword
            start_page = self.start_page
            end_page = self.end_page
            sort_type_str = self.sort_type
            get_user_details = self.get_user_details
            download_images = self.download_images
            image_max_width = self.image_max_width
            image_max_height = self.image_max_height
            
            print(f"🎯 输入参数:")
            print(f"   关键词: {keyword}")
            print(f"   页数范围: {start_page} - {end_page}")
            print(f"   排序方式: {sort_type_str}")
            print(f"   获取用户详情: {get_user_details}")
            print(f"   下载图片: {download_images}")
            
            # 转换排序类型
            sort_type = self.get_sort_value(sort_type_str)
            print(f"🎯 排序类型转换: {sort_type_str} -> {sort_type}")
            
            # 获取数据
            response_data_list = self.fetch_data(keyword, start_page, end_page, sort_type)
            
            if not response_data_list:
                error_msg = "没有获取到任何响应数据"
                print(f"❌ {error_msg}")
                return Data(value={
                    "status": "no_data",
                    "message": error_msg,
                    "total_items": 0,
                    "debug_info": "API请求失败，没有返回任何数据"
                })
            
            # 提取数据
            extracted_data = self.extract_all_data(response_data_list)
            
            if not extracted_data:
                error_msg = "没有提取到有效数据"
                print(f"❌ {error_msg}")
                
                # 提供详细的调试信息
                debug_info = {
                    "response_count": len(response_data_list),
                    "response_samples": []
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
                
                return Data(value={
                    "status": "no_data", 
                    "message": error_msg,
                    "total_items": 0,
                    "debug_info": debug_info
                })
            
            # 构建结果
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
                    "get_user_details": get_user_details,
                    "download_images": download_images
                }
            }
            
            print(f"✅ 爬取完成！共获取 {len(extracted_data)} 条数据")
            
            return Data(value=result)
            
        except Exception as e:
            error_msg = f"爬取过程中发生错误: {str(e)}"
            print(f"❌ {error_msg}")
            import traceback
            print(f"❌ 错误详情: {traceback.format_exc()}")
            
            return Data(value={
                "status": "error",
                "message": error_msg,
                "total_items": 0,
                "debug_info": traceback.format_exc()
            })