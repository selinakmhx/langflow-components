from langflow.custom import Component
from langflow.io import DataInput, Output
from langflow.schema import Data
from typing import Any, List

class DataFormatter(Component):
    display_name = "数据格式化器"
    description = "从输入数据中提取 data 数组，直接输出为 results 格式，不做任何字段处理。"
    icon = "git-merge-line"
    name = "DataFormatter"

    inputs = [
        DataInput(
            name="input_data",
            display_name="输入数据(Data)",
            info='接收来自"图文全勾选输出"或"视频无任何勾选"等组件的原始数据。',
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="格式化数据", name="output_data", method="run"),
    ]

    def run(self) -> Data:
        input_data = self.input_data

        if not input_data or not hasattr(input_data, 'data'):
            self.status = "输入数据为空或格式不正确"
            return Data(data={"results": []})

        raw_data = input_data.data
        records: List[Any] = []

        try:
            if isinstance(raw_data, dict):
                if 'value' in raw_data and isinstance(raw_data['value'], dict) and 'data' in raw_data['value']:
                    records = raw_data['value']['data']
                    if not isinstance(records, list):
                        raise ValueError("键 'data' 对应的值不是一个列表。")
                elif 'data' in raw_data and isinstance(raw_data['data'], list):
                    records = raw_data['data']
                else:
                    raise ValueError("输入字典中未找到预期的 'value' -> 'data' 或 'data' 结构。")
            elif isinstance(raw_data, list):
                records = raw_data
            else:
                raise TypeError("输入数据不是一个有效的字典或列表。")

            self.status = f"成功提取 {len(records)} 条记录。"

        except (TypeError, ValueError, KeyError) as e:
            self.status = f"处理输入数据时出错: {str(e)}"
            records = []
        
        # 直接输出，不做任何处理
        output_payload = {
            "results": records
        }

        self.status = f"成功输出 {len(records)} 条数据"
        return Data(data=output_payload)