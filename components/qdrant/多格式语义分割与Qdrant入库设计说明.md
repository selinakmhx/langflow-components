中文语义友好的推荐策略

- 统一清洗与分块（按文件类型分流，最终合流入库）：
  - PDF/Docx/图片：
    - 首选 Docling 的 standard 管线，默认关闭 OCR，仅在检测为扫描件时启用 OCR。
    - 导出结构化（ export_to_dict ）后，按“标题层级->段落->页面”构建分块，保留元数据 page_no/section/level 。
  - txt/md：
    - 直接读取，先做正则清洗（去控制字符、重复页眉页脚），以中文标点分句（如 。？！； + 换行），再做长度聚合（推荐 800–1200 字，重叠 100–200 字）。
  - json/csv：
    - 结构化处理：为每一条记录生成一个“知识条目”，把主要字段拼接成检索文本，同时保留原始字段为 payload。表格字段可同步生成 Markdown 表格文本，兼顾可读性。
- 语言检测与中文优先：
  - 对每条分块做轻量语言检测（如字符分布或简繁体词典命中），标记 language=zh ，为中文块选择中文/多语嵌入模型。
- 元数据统一：
  - 每个分块的 payload 建议包含： source 、 type 、 language 、 title 、 section 、 page_no 、 chunk_id 、 doc_id 、 created_at 。
- 嵌入与向量库：
  - 中文/多语模型建议： bge-m3 （多语、强检索）、 m3e-base （中文向好）、 gte-large-zh （中文文本匹配）等。
  - 保持 collection 的向量维度与模型一致（如 bge-m3 为 1024 维， m3e-base 为 768 维），对不同维度的模型用不同 collection 或统一选型。
依赖与安装建议

- Docling（用于 PDF/Office/图片的版面解析）：
  - pip install docling docling-core
- OCR（仅在确有扫描件/图片识别需求时）：
  - 轻量方案： pip install easyocr ；若提示需 PyTorch，可安装 CPU 版： pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
  - 其他 OCR 引擎 Docling 也有支持，具体名称以官方文档为准。
- 中文分块与清洗（可选）：
  - 你可以使用纯正则/自定义逻辑，无需额外库；如需更精细，可选择 zhon 或 jieba 做辅助。
- 向量库与嵌入：
  - Qdrant Python 客户端： pip install qdrant-client
  - 嵌入模型：根据你选型安装相应包或调用云服务 SDK。
如果不装这些依赖的替代工具

- unstructured ：多格式分块库，适配面广，入门快。 pip install unstructured
- PDF 专用：
  - pymupdf 或 pdfplumber ：适合抽文本与部分结构，但版面语义保留不如 Docling。
- OCR 中文：
  - paddleocr 或 tesseract + chi_sim ：中文识别做得不错，但与版面结构结合需要额外工程。
- 前台自定义组件思路：
  - 在上传后按类型做分流处理：文本类组件、结构化表格组件、文档版面组件；统一输出“分块 + payload”，前台只负责路由和配置参数，解析在后端或子进程执行。
向量数据库接入建议

- 集合设计：
  - 单集合（统一维度，同模型）或多集合（按模型/领域分）：推荐单集合提高检索统一性。
- Payload 字段：
  - 最少包含 text + 元数据（见上），并存 doc_id 以便整文召回。
- 检索与重排：
  - 向量检索 + 关键词（Hybrid），对中文场景更稳。
  - 可选 reranker（如 bge-reranker-large ）提升语义相关度。
- 代码参考：
  - 你的项目已有 Qdrant 组件雏形（ qdrant/local（unuse）/qdrant.py:1–15 ），也可用 Langflow 自带 Qdrant 集成。
我们已做的优化（避免安装 EasyOCR 也能跑）

- 默认 OCR 改为关闭： qdrant/文件输入组件（自带）.py:107–114 现在 value="None" 。
- 当管线是 standard 时，不再强制把 OCR 设为 easyocr： qdrant/文件输入组件（自带）.py:200–206 。
- 子进程里若选择了 easyocr 但未安装，会自动禁用 OCR 继续转换： qdrant/文件输入组件（自带）.py:373–386 。
- 若 Docling 报“EasyOCR 未安装”，父进程自动重试并关闭 OCR： qdrant/文件输入组件（自带）.py:537–559 。
结论与建议

- 对你的混合文件集，Docling“很有用”，尤其是 PDF/Docx/图片的结构保留与分块质量，对后续中文语义检索帮助明显。
- 最小可用方案：不开启 OCR 也能跑（已优化）；遇到扫描件时再加装 easyocr/torch ，并按需启用。
- 如果团队不愿安装 Docling，亦可用 unstructured + 轻量解析（pymupdf/pdfplumber）+ 自定义中文分块 的组合，但结构保留与表格抽取效果会打一定折扣。
下一步（建议给部署同学的话）

- 必备： pip install docling docling-core qdrant-client
- 可选（有扫描件/图片文字识别需求时）： pip install easyocr ；如需 CPU 版 PyTorch： pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
- 选定嵌入模型并统一维度（如 bge-m3=1024 或 m3e-base=768 ），创建对应 Qdrant collection。
- 前台上传组件保持现状；批量文件时走轻量解析路径，单文件需要结构化时用高级解析。若你希望“批量也用高级解析”，我可以把组件改成逐文件串行调用 Docling 子进程并汇总输出。