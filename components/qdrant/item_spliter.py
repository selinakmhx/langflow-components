import json
from langflow.custom.custom_component.component import Component
from langflow.io import HandleInput, Output, MessageTextInput
from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message

class ItemSplitterComponent(Component):
    display_name: str = "按条目分割"
    description: str = "将输入的JSON数据按指定键的数组中的条目进行分割。"
    icon = "scissors-line-dashed"
    name = "ItemSplitter"

    inputs = [
        HandleInput(
            name="input_data",
            display_name="输入数据",
            info="包含JSON文本的Data、Message或DataFrame。",
            input_types=["Data", "Message", "DataFrame", "list[Data]"],
            required=True,
        ),
        MessageTextInput(
            name="json_key",
            display_name="JSON键",
            info="包含条目列表的JSON键。",
            value="results",
            advanced=False,
        ),
        MessageTextInput(
            name="text_key",
            display_name="文本键",
            info="当输入是DataFrame时，用来指定包含JSON文本的列名。",
            value="text",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="条目块", name="items", method="split_items"),
    ]

    def _process_dict(self, json_data: dict):
        """辅助函数，用于处理字典并提取条目。"""
        items_list = json_data.get(self.json_key)
        if not isinstance(items_list, list):
            return []

        new_items = []
        for item in items_list:
            # 将每个条目转换为JSON字符串作为输出的文本
            if isinstance(item, dict):
                item_text = json.dumps(item, ensure_ascii=False, indent=2)
            else:
                item_text = str(item)
            # 将原始条目字典本身作为元数据
            new_items.append(Data(text=item_text, data=item if isinstance(item, dict) else {'value': item}))
        return new_items

    def split_items(self) -> DataFrame:
        """
        根据JSON数组中的条目分割输入数据。
        """
        if self.input_data is None:
            raise ValueError("未提供输入数据。")

        all_items = []
        # 统一处理列表和单个输入
        inputs_to_process = self.input_data if isinstance(self.input_data, list) else [self.input_data]

        for single_input in inputs_to_process:
            if isinstance(single_input, Data):
                # 假设 .data 包含已解析的JSON字典
                if isinstance(single_input.data, dict):
                    all_items.extend(self._process_dict(single_input.data))
            elif isinstance(single_input, Message):
                try:
                    json_data = json.loads(single_input.text)
                    all_items.extend(self._process_dict(json_data))
                except (json.JSONDecodeError, TypeError):
                    # 如果Message内容不是有效的JSON，则跳过
                    continue
            elif isinstance(single_input, DataFrame):
                if self.text_key not in single_input.df.columns:
                    raise ValueError(f"DataFrame中未找到指定的文本键 '{self.text_key}'。")
                for text_content in single_input.df[self.text_key].tolist():
                    try:
                        json_data = json.loads(text_content)
                        all_items.extend(self._process_dict(json_data))
                    except (json.JSONDecodeError, TypeError):
                        # 如果单元格内容不是有效的JSON，则跳过
                        continue
        
        if not all_items:
            self.status = "未从输入中分割出任何条目。"

        return DataFrame(all_items)