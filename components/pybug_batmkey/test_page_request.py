#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import os

# 添加父目录到路径，以便导入trycode
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from components.pybug_batmkey.trycode import XiaohongshuScraper

def test_page_request():
    """测试页数请求功能"""
    print("🚀 开始测试页数请求功能...")
    
    # 创建爬虫实例
    scraper = XiaohongshuScraper()
    
    # 测试参数
    test_keyword = "项链"
    test_start_page = 1
    test_end_page = 2  # 只请求2页进行测试
    test_sort_type = 2  # 最热排序
    
    print(f"📊 测试参数:")
    print(f"   关键词: {test_keyword}")
    print(f"   起始页: {test_start_page}")
    print(f"   结束页: {test_end_page}")
    print(f"   排序方式: {test_sort_type}")
    print()
    
    try:
        # 调用fetch_data方法
        print("📡 开始请求数据...")
        response_data_list = scraper.fetch_data(test_keyword, test_start_page, test_end_page, test_sort_type)
        
        print(f"✅ 请求完成，共获取 {len(response_data_list)} 页数据")
        
        # 检查是否只请求了指定的页数
        expected_pages = test_end_page - test_start_page + 1
        if len(response_data_list) == expected_pages:
            print(f"✅ 页数正确: 请求了 {expected_pages} 页，实际返回 {len(response_data_list)} 页")
        else:
            print(f"❌ 页数错误: 期望 {expected_pages} 页，实际返回 {len(response_data_list)} 页")
        
        # 保存结果到JSON文件
        output_file = "/Users/macmima1234/code/components/components/pybug_batmkey/文档/page_request_test_result.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(response_data_list, f, ensure_ascii=False, indent=2)
        
        print(f"💾 结果已保存到: {output_file}")
        
        # 分析每页的数据结构
        print("\n📊 数据分析:")
        for i, page_data in enumerate(response_data_list, 1):
            if isinstance(page_data, dict):
                items_count = len(page_data.get('data', {}).get('items', [])) if 'data' in page_data else 0
                print(f"   第 {i} 页: {items_count} 条笔记")
                
                # 检查是否有has_more字段
                has_more = page_data.get('data', {}).get('has_more', False)
                print(f"     是否有更多数据: {has_more}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        print(f"❌ 错误详情: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = test_page_request()
    if success:
        print("\n🎉 页数请求测试完成！")
    else:
        print("\n💥 页数请求测试失败！")
        sys.exit(1)