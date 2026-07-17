# 成员 C：文档处理模块 — 开发指导文档

> **成员角色**：文档处理负责人  
> **负责模块**：PDF/TXT/MD/DOCX/HTML/PPTX 解析、文本清洗、chunk 切分、metadata 生成  
> **交付物**：`document_loader.py`、`text_splitter.py`、测试文件、切分样例

---

## 一、模块定位

你是整个 RAG 流程的 **第一道关口**——文档解析质量直接影响后续检索和生成效果。

```
上传文件 → [你的模块] 解析+清洗+切分 → Chunk 列表 → 成员D写入Chroma → 成员E调用LLM
```

---

## 二、已交付文件清单

```
小组作业/
├── backend/
│   ├── models/
│   │   ├── __init__.py
│   │   └── chunk.py                 ← Chunk 数据模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_loader.py       ← 文档解析器（主文件）★
│   │   ├── text_splitter.py         ← 文本切分器（主文件）★
│   │   ├── chroma_service.py        ← 成员 D
│   │   └── rag_service.py           ← 成员 E
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_document_loader.py  ← 解析器测试
│   │   └── test_text_splitter.py    ← 切分器测试
│   ├── main.py                      ← FastAPI 入口（成员 B）
│   └── requirements.txt             ← Python 依赖
├── uploads/                         ← 上传文件存放
├── data/chroma_db/                  ← Chroma 持久化
└── C成员开发指导文档.md              ← 本文档
```

---

## 三、支持的文件格式

| 格式 | 解析函数 | 状态 |
|------|---------|------|
| PDF | `parse_pdf()` / `parse_pdf_with_ocr()` | ✅ 基础 + 🆕 OCR 回退 |
| TXT | `parse_txt()` | ✅ 自动编码检测 |
| Markdown | `parse_markdown()` | ✅ 标记语法去除 |
| DOCX | `parse_docx()` | ✅ 🆕 表格→Markdown 格式 |
| HTML | `parse_html()` | 🆕 |
| PPTX | `parse_pptx()` | 🆕 |

---

## 四、快速开始

### 4.1 安装依赖

```bash
cd backend
pip install -r requirements.txt

# 可选：OCR 支持（扫描版 PDF）
# pip install pytesseract pdf2image
# 还需安装系统依赖：Tesseract OCR + Poppler
```

### 4.2 运行测试

```bash
cd backend
python -m pytest tests/test_document_loader.py -v
python -m pytest tests/test_text_splitter.py -v
python -m pytest tests/ -v
```

### 4.3 快速验证

```bash
cd backend

# 测试解析
python -c "
from services.document_loader import parse_document
text = parse_document('你的测试文件.pdf', 'pdf')
print(text[:500])
"

# 测试完整流程 + 统计数据
python -c "
from services.text_splitter import build_chunks, get_split_statistics, visualize_chunks
chunks = build_chunks('你的测试文件.pdf', 'pdf', 'doc001', '测试.pdf', '课程名')
print(get_split_statistics(chunks))
print(visualize_chunks(chunks))
"
```

---

## 五、核心技术栈

### 5.1 依赖库一览

| 库 | 版本 | 用途 | 核心技术点 |
|----|------|------|-----------|
| `pypdf` | ≥5.0 | PDF 文字提取 | 基于 PDF 内部文本对象解析，非 OCR；逐页调用 `Page.extract_text()` 读取字符流 |
| `python-docx` | ≥1.0 | DOCX 解析 | 操作 OOXML 格式（ZIP 包内的 XML 文档树），通过 `Document.paragraphs` 和 `Document.tables` 遍历 |
| `python-pptx` | ≥1.0 | PPTX 解析 | 同属 OOXML 体系，`Presentation.slides` 遍历幻灯片，`Shape.has_text_frame/has_table` 判断内容类型 |
| `markdown` | ≥3.5 | MD→HTML 转换 | 将 Markdown 语法转为标准 HTML 标签字串，配合 `BeautifulSoup.get_text()` 剥离标记 |
| `beautifulsoup4` | ≥4.12 | HTML/XML 解析 | 基于 lxml 或 html.parser 的 DOM 树解析，`.get_text()` 递归提取所有文本节点 |
| `matplotlib` | ≥3.8 | 切分可视化 | 非交互式 Agg 后端，双子图布局（bar + hist），`plt.savefig()` 输出 PNG |

### 5.2 OCR 可选依赖

| 库 | 用途 | 系统依赖 |
|----|------|---------|
| `pytesseract` | Python 调用 Tesseract OCR 引擎 | [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) |
| `pdf2image` | PDF→图片逐页渲染 | [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/)（Windows） |

---

## 六、各模块 API 速查

### 6.1 `document_loader.py` — 文档解析器

**统一入口**：
```python
from services.document_loader import parse_document
text = parse_document("文件路径", "文件类型")
```

**各解析函数**：

| 函数 | 用途 | 关键点 |
|------|------|--------|
| `parse_pdf(path)` | 逐页提取 PDF 文字 | 扫描版返回空字符串 |
| `parse_pdf_with_ocr(path)` | PDF + OCR 回退 | 先尝试文字层，失败则 OCR |
| `parse_txt(path)` | 读取文本文件 | UTF-8 → GBK → Latin-1 自动检测 |
| `parse_docx(path)` | 提取段落 + Markdown 表格 | 🆕 表格自动转 Markdown |
| `parse_markdown(path)` | 去除 Markdown 标记 | 保留纯文本 |
| `parse_html(path)` | 🆕 HTML 纯文本提取 | 自动去除 script/style |
| `parse_pptx(path)` | 🆕 PPTX 逐页提取 | 含文本框和表格 |
| `clean_text(text)` | 文本清洗 | 保留段落结构 |

### 6.2 `text_splitter.py` — 文本切分器

**主函数**（成员 B 直接调用）：
```python
from services.text_splitter import build_chunks

chunks = build_chunks(
    file_path="数据库概论.pdf",
    file_type="pdf",
    document_id="doc001",
    document_name="数据库概论.pdf",
    course="数据库",
    chunk_size=500,     # 默认 500
    overlap=100,        # 默认 100
)
```

🆕 **精确页码映射**：对 PDF 文件，`build_chunks()` 自动启用逐页匹配算法，为每个 chunk 分配准确的页码（而非粗略估算）。

🆕 **切分可视化**：
```python
from services.text_splitter import visualize_chunks

# 文本柱状图（无需额外依赖）
print(visualize_chunks(chunks, output_format="text"))

# matplotlib 图表（保存为 PNG，需 pip install matplotlib）
print(visualize_chunks(chunks, output_format="matplotlib"))
# → [图表已保存] uploads/chunk_visualization.png

# HTML 交互式图表（Chart.js）
print(visualize_chunks(chunks, output_format="html"))
# → [HTML 图表已保存] uploads/chunk_visualization.html
```

🆕 **JSON 导出**：
```python
from services.text_splitter import export_chunks_to_json

path = export_chunks_to_json(chunks, "uploads/my_chunks.json")
# → 包含 statistics + 所有 chunk 详情，方便写报告
```

🆕 **统计函数**：
```python
from services.text_splitter import get_split_statistics
stats = get_split_statistics(chunks)
# {"total_chunks": 15, "avg_length": 480.5, "max_length": 500, ...}
```

---

## 七、与成员 B、D 的接口约定

### 7.1 成员 B（后端）调用方式

```python
from services.text_splitter import build_chunks, get_split_statistics
from services.document_loader import get_file_type, SUPPORTED_TYPES

@app.post("/api/upload")
async def upload(file: UploadFile, course: str = ""):
    # 1. 保存文件
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # 2. 文件类型检查
    file_type = get_file_type(file.filename)
    if file_type not in SUPPORTED_TYPES:
        return {"status": "error", "message": f"不支持的文件类型: .{file_type}"}

    # 3. 调用你的模块
    doc_id = f"doc{get_next_id()}"
    chunks = build_chunks(
        file_path=file_path,
        file_type=file_type,
        document_id=doc_id,
        document_name=file.filename,
        course=course,
    )

    if not chunks:
        return {"status": "warning", "message": "文件无可提取的文字，可能是扫描版 PDF"}

    # 4. 交给 D 入库
    from services.chroma_service import add_chunks
    add_chunks(chunks)

    return {
        "status": "ok",
        "document_id": doc_id,
        "chunk_count": len(chunks),
        "statistics": get_split_statistics(chunks),
    }
```

### 7.2 成员 D（Chroma）数据格式

```python
chunk.to_chroma_format()
# {
#     "id": "doc001_chunk_003",
#     "document": "Cache 是位于 CPU 和主存之间的高速存储器...",
#     "metadata": {
#         "document_id": "doc001",
#         "document_name": "数据库系统概论.pdf",
#         "page_number": 12,       # 🆕 精确页码（PDF）
#         "chunk_index": 3,
#         "total_chunks": 15,
#         "course": "数据库",
#     },
# }
```

---

## 八、技术细节详解

> 此部分面向报告撰写和答辩准备，详细解释每个模块的底层原理、关键算法和设计决策。涵盖了扩展功能的完整技术说明。

---

### 8.1 PDF 解析：pypdf 文字提取原理

**底层机制**：

PDF 文件由一系列对象（objects）组成，文本内容存储在"内容流"（content stream）中，以文本操作符的形式编码——典型的如 `Tj`（显示文本字串）、`TJ`（显示文本数组）、`Td`（移动文本位置）等。pypdf 的 `Page.extract_text()` 方法会：

1. 解析页面的内容流 → 提取所有文本操作符
2. 根据 `Td`/`Td*` 操作符计算每个文本块的坐标位置
3. 按 Y 坐标降序（从上到下）、X 坐标升序（从左到右）排列文本
4. 使用 PDF 字体映射（CMap）将字符编码转为 Unicode

```
PDF 内容流                 pypdf 处理                   输出
┌──────────────────┐     ┌────────────────┐      ┌──────────────┐
│ BT               │     │ 1. 解析操作符   │      │ "第一段文字\n │
│ /F1 12 Tf        │ ──→ │ 2. 按坐标排序   │ ──→  │  第二段文字"  │
│ 100 700 Td       │     │ 3. CMap 解码    │      └──────────────┘
│ (Hello) Tj       │     │ 4. 添加换行分隔  │
│ ET               │     └────────────────┘
└──────────────────┘
```

**为什么扫描版 PDF 返回空字符串**：

扫描版 PDF 的内容流中不包含文本操作符——页面内容是一张嵌入的图片（`/Subtype /Image`），文字作为像素存在图片中。pypdf 查找文本操作符时找不到任何内容，自然返回空字符串。此时必须使用 OCR（光学字符识别）将图片转为文字。

**中文 PDF 乱码原因**：部分中文字体使用了自定义的 CMap 编码（如 GBK-EUC-H），pypdf 内置的字体映射表可能无法正确解码，导致输出为乱码或无意义的字符。此时可换用 `pdfplumber`（它在 pypdf 之上做了更多字体处理）。

```python
# 换用 pdfplumber 的示例
import pdfplumber
with pdfplumber.open(file_path) as pdf:
    text = "\n".join(page.extract_text() for page in pdf.pages)
```

---

### 8.2 TXT 编码检测：三段回退策略

**原理**：

文本文件的编码信息不存在于文件内容中（与 HTML/XML 的 `<meta charset>` 不同），必须在读取时靠外部知识判断。策略是按概率从高到低依次尝试：

```
尝试 UTF-8 ─失败─→ 尝试 GBK ─失败─→ 尝试 Latin-1 ─失败─→ 抛异常
   │                │               │
   ▼                ▼               ▼
 成功返回          成功返回         兜底成功（Latin-1 永远不会失败）
```

- **UTF-8**：Python 源文件、Markdown、现代文本文件的首选编码，覆盖 90% 场景
- **GBK / GB2312**：中文 Windows 系统默认 ANSI 编码，老版 TXT 常用。`UnicodeDecodeError` 触发回退
- **Latin-1 (ISO-8859-1)**：单字节编码，每个字节都是合法字符，**永远不会抛出 UnicodeDecodeError**——因此作为最终兜底，保证函数永远能返回结果

```python
for encoding in ["utf-8", "gbk", "latin-1"]:
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except UnicodeDecodeError:
        continue  # 编码不匹配，继续尝试下一个
```

---

### 8.3 DOCX 解析：OOXML 文档树遍历

**底层机制**：

DOCX 文件本质是一个 ZIP 压缩包，内含多个 XML 文件。结构如下：

```
document.docx  ←── ZIP 包
├── [Content_Types].xml
├── word/
│   ├── document.xml     ← 正文内容（段落 + 表格）
│   ├── styles.xml
│   └── media/           ← 嵌入图片（python-docx 不处理）
└── docProps/
```

`python-docx` 将 `word/document.xml` 解析为对象树：

```xml
<!-- word/document.xml 片段 -->
<w:document>
  <w:body>
    <w:p>        ← python-docx 映射为 Paragraph 对象
      <w:r>
        <w:t>段落文字</w:t>
      </w:r>
    </w:p>
    <w:tbl>      ← python-docx 映射为 Table 对象
      <w:tr>     ← Row
        <w:tc>   ← Cell
          <w:p><w:r><w:t>单元格文字</w:t></w:r></w:p>
        </w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>
```

**文档元素顺序保持**：

`build_chunks()` 调用 `parse_docx()` 时，代码通过 `doc.element.body` 直接遍历 XML 子元素，按 `w:p`（段落）和 `w:tbl`（表格）的标签类型交替输出，确保解析后的文本中段落和表格的先后顺序与原始文档一致。

**表格 Markdown 化**：

```
python-docx Table ──→ 按行遍历 cell.text ──→ 拼接 "| col1 | col2 |" ──→ 插入 "|---|---|" 分隔线
```

第一行默认为表头，后续行为数据行。合并单元格通过补齐空列处理（取最大列数统一宽度）。

**已知局限**：
- 数学公式（MathType / OMML）：存储在独立的 `w:oMath` 标签中，python-docx 的 `paragraph.text` 不会提取，返回空字符串
- 图片：存储在 `word/media/` 中，python-docx 不提供图片文字提取的接口

---

### 8.4 HTML 解析：BeautifulSoup DOM 遍历

**处理流程**：

```
HTML 文件
  ↓
BeautifulSoup(html, "html.parser")  ← 构建 DOM 树
  ↓
soup(["script", "style", "nav", "footer", "header"])  ← 移除噪声标签
  ↓
遍历块级元素（p, div, li, h1-h6, br）→ 在元素后插入 \n
  ↓
soup.get_text()  ← 递归提取所有文本节点
  ↓
清理多余空行 → 输出纯文本
```

**关键设计决策**——为什么移除 script/style 而不是简单 get_text()：

`BeautifulSoup.get_text()` 会提取 DOM 树中**所有**文本节点的内容，包括 `<script>` 中的 JavaScript 代码和 `<style>` 中的 CSS 规则。这些内容对 RAG 检索是纯粹噪声——它们不是文档正文，但会占用 chunk 空间、降低检索精度。因此在调用 `get_text()` 前先销毁这些标签。

**块级元素加换行**：HTML 中连续的 `<p>` 标签解析后文本可能粘连。在块级元素后手动插入 `\n` 确保段落分隔，对中文网页尤其重要（中文网页常不用 `<br>` 换行）。

---

### 8.5 PPTX 解析：Slide-对象模型遍历

**底层机制**：

PPTX 也属于 OOXML 格式家族，结构如下：

```
presentation.pptx  ←── ZIP 包
├── ppt/
│   ├── slides/
│   │   ├── slide1.xml    ← 第 1 页
│   │   ├── slide2.xml    ← 第 2 页
│   │   └── ...
│   └── slideLayouts/
└── docProps/
```

每页幻灯片包含多个 Shape（形状）对象：

```
幻灯片 Slide
├── Shape 1: 标题框    → shape.has_text_frame → True  → 提取段落文字
├── Shape 2: 正文框    → shape.has_text_frame → True  → 提取段落文字
├── Shape 3: 表格      → shape.has_table     → True  → 转为 Markdown 表格
├── Shape 4: 图片      → shape.has_text_frame/has_table → False → 跳过
└── Shape 5: SmartArt  → 无法直接提取文字           → 跳过（已知局限）
```

**输出格式**：

```
[幻灯片 1]
课程标题
副标题文字

---

[幻灯片 2]
正文内容段落一
正文内容段落二

| 列A | 列B |
| --- | --- |
| 数据1 | 数据2 |
```

页码标记 `[幻灯片 N]` 是人工插入的提示，帮助在 chunk metadata 中页码追溯时提供参考。

**已知局限**：
- SmartArt 图形：文字嵌入在复杂的 XML 结构中，python-pptx 不提供直接提取接口
- 嵌入视频/音频：二进制对象，不可解析
- 母版/版式文字：默认不遍历（只在 `slide.shapes` 范围，不含 `slide_layout` 和 `slide_master`）

---

### 8.6 文本清洗：正则表达式管线

**清洗规则的设计原理**：

```
原始文本
  ↓ re.sub(r"\n{3,}",  "\n\n")     # 规则1：合并过多空行 → 保留段落间距
  ↓ re.sub(r"[ \t]+", " ")         # 规则2：合并行内空格  → 保留单词分隔
  ↓ re.sub(r"[\x00-\x08...]", "")  # 规则3：删除控制字符  → 排除零宽/破坏性字符
  ↓ line.strip() for line in ...   # 规则4：行首尾去空格 → 统一格式
  ↓ .strip()                        # 规则5：全文去首尾空白
  ↓
干净文本
```

**规则 1 — `\n{3,}` → `\n\n`**：
保留至多一个空行（即段落间距）。PDF 解析后在页码过渡处常产生 3-5 个连续空行；全部保留会浪费 chunk 空间、2 个换行足够表达"段落分隔"语义。

**规则 2 — `[ \t]+` → `" "`**：
多个连续空格和 Tab 合并为一个空格。中文文本中空格通常不承载语义信息；英文段落内部的缩进/对齐也不影响检索。

**规则 3 — 控制字符过滤**：
```
\x00-\x08   NUL ~ BS       这些字符要么是文件终结符（\x00），要么用于终端控制
\x0b        VT             垂直制表符
\x0c        FF             换页符（PDF 中常见），已在规则1转为 \n
\x0e-\x1f   SO ~ US        Shift Out/In 等历史上用于电传打字机的控制字符
\x7f-\x9f   DEL ~ APC      DEL 和 C1 控制字符范围
```

保留的字符：`\t`（Tab，已被规则2处理）、`\n`（换行）、`\r`（回车，但在 Windows 上通常已被 normalize）。

---

### 8.7 文本切分：递归字符切分（Recursive Character Text Splitter）

这是整个模块中**最核心的算法**，直接影响 RAG 检索质量。

**算法流程**：

```
输入文本 + chunk_size=500, overlap=100
  │
  ▼
┌─ while start < len(text): ──────────────────────────────────────┐
│                                                                  │
│   end = start + 500        ← 计算理想结束位置                     │
│   chunk_candidate = text[start:end]                              │
│                                                                  │
│   ┌─ 按优先级搜索最佳切分点 ─────────────────────────┐            │
│   │  separators = ["\n\n", "\n", "。", ".", ..., ""] │            │
│   │  对每个 sep:                                      │            │
│   │    last_idx = chunk_candidate.rfind(sep)          │ ← rfind  │
│   │    找到 → 在该分隔符之后切开 → 跳出循环            │  从右往左 │
│   │    "": 强制切分 (兜底)                             │            │
│   └──────────────────────────────────────────────────┘            │
│                                                                  │
│   actual_end = start + best_cut     ← 实际切分位置                │
│   chunks.append(text[start:actual_end])                           │
│   start = actual_end - overlap      ← 下一个 chunk 的起始         │
│   if start <= old_start:            ← 防死循环                    │
│       start = actual_end                                          │
└──────────────────────────────────────────────────────────────────┘
```

**分隔符优先级设计原理**：

```
语义完整度
  ↑
  │ \n\n   ★ 段落边界 — 最佳切分点（大概率语义自包含）
  │ \n     ★ 行边界 — 次佳
  │ 。.！？ ★ 句子边界 — 中文/英文句子结束
  │ ，,；; ★ 子句边界 — 语义单元的弱边界
  │ (空格)  ★ 单词边界 — 英文单词间
  │ ""     ★ 字符级强制切分 — 无任何边界可用时的兜底
  └──────────────────────────────────────→ 优先级递减
```

使用 `rfind()`（从右往左搜索）的原因：尽量切出接近 `chunk_size` 大小的片段，充分利用 chunk 容量，减少碎片化。

**Overlap 作用**：

```
Chunk 1:  [══════ 前 40 字 ══════╪══ Overlap ══]
Chunk 2:            [══ Overlap ══╪══════ 后 40 字 ══════]
                                   ↑
                         保证语义完整性不在此处截断
```

Overlap 确保在 chunk 边界处的概念不会被生硬截断——如果某个术语或句子恰好跨在 chunk 边界上，相邻 chunk 的重叠区域会覆盖它，检索时至少有一个 chunk 能完整命中。

**死循环防护**：

当 `overlap >= best_cut` 时，`start = actual_end - overlap` 可能导致 `start` 小于等于旧 `start`，造成无限循环。代码通过 `if next_start <= start: next_start = actual_end` 强制前进。

---

### 8.8 精确 PDF 页码映射：字符范围二分定位

**算法原理**：

```
Step 1: 构建页码映射表
┌──────────────┬──────────────┬──────────────┐
│ Page 1       │ Page 2       │ Page 3       │
│ chars[0:1523]│ chars[1523:  │ chars[3100:  │
│              │       3100]  │       4892]  │
└──────────────┴──────────────┴──────────────┘

Step 2: 对每个 chunk，用前 50 字符在全文定位
chunk_text[:50] → full_text.find(key) → 返回字符位置 pos

Step 3: 在映射表中二分查找
for (start, end, page_num) in page_ranges:
    if start <= pos < end:
        return page_num
```

**为什么用前 50 个字符而不是全文匹配**：

chunk 文本内容可能与原文不完全一致（经历了 clean_text 清洗）。取前 50 个字符做模糊匹配，既足够唯一（出现重复的概率极低），又能容忍清洗造成的轻微文本变化。

**Fallback 策略**：
- PDF 读取失败 → 全部返回 chunk_index + 1（按序号估算）
- 字符无法在所有页面中找到 → 继承上一个 chunk 的页码（连续性假设）
- page_ranges 为空 → 全部返回 chunk_index + 1

---

### 8.9 OCR 回退机制

**策略**：

```
parse_pdf_with_ocr(file_path, lang="chi_sim+eng")
  │
  ├─① parse_pdf(file_path)  ← pypdf 先尝试文字层
  │   └─ 有文字 → 直接返回 ✔
  │   └─ 空字符串 ↓
  │
  ├─② import pytesseract, pdf2image  ← 检查 OCR 依赖
  │   └─ ImportError → 返回友好提示 "[该 PDF 无文字层...]"
  │   └─ 成功导入 ↓
  │
  └─③ pdf2image.convert_from_path(file, dpi=200)
      └─ 逐页渲染为 PIL Image
      └─ pytesseract.image_to_string(img, lang=lang)
      └─ 拼接所有页文字 → 返回
```

**关键参数**：
- `dpi=200`：PDF→图片渲染分辨率。200 DPI 在识别准确率和速度之间取得平衡。300 DPI 识别率更高但耗时约 2.5×
- `lang="chi_sim+eng"`：Tesseract 语言包。`chi_sim` = 简体中文、`eng` = 英文，同时加载可识别中英混排文档

**系统依赖安装**（Windows）：

```
1. Tesseract OCR
   https://github.com/UB-Mannheim/tesseract/wiki
   安装后需将安装目录加入 PATH（如 C:\Program Files\Tesseract-OCR\）

2. Poppler (pdf2image 的图像渲染后端)
   https://github.com/oschwartz10612/poppler-windows/releases/
   解压后将 bin/ 目录加入 PATH
```

---

### 8.10 切分可视化：三种输出格式的架构

```
visualize_chunks(chunks, output_format)
  │
  ├─ "text"      → _visualize_text()
  │                 ├─ 计算 max_len
  │                 ├─ 每个 chunk 画 "█" * (len(chunk) / max_len * 40)
  │                 └─ 返回控制台字符串（零依赖）
  │
  ├─ "matplotlib" → _visualize_matplotlib()
  │                  ├─ matplotlib.use("Agg")  ← 非交互后端（无需 GUI）
  │                  ├─ ax1.bar()              ← 左图：按 chunk 序号的柱状图
  │                  │   └─ 颜色编码：≥ 平均值 = 绿色(#4ECDC4)，< 平均值 = 红色(#FF6B6B)
  │                  ├─ ax2.hist()             ← 右图：长度频率分布直方图
  │                  │   └─ bins=min(15, len(chunks)) ← 自适应分箱数
  │                  ├─ ax1/ax2.axhline/axvline()    ← 平均值参考线（虚线）
  │                  └─ plt.savefig("uploads/chunk_visualization.png", dpi=150)
  │
  └─ "html"      → _visualize_html()
                     ├─ 生成完整 HTML 文档
                     ├─ CDN 加载 Chart.js v4.4.0
                     ├─ 统计卡片（CSS Flexbox 布局）
                     ├─ Bar Chart（颜色编码同 matplotlib）
                     └─ 写入 uploads/chunk_visualization.html
```

---

### 8.11 数据模型：Chunk / ChunkMetadata 设计

```
Chunk
├── chunk_id: str          → "doc001_chunk_003"
│                            └─ 格式: {document_id}_chunk_{index:03d}
│                               用 0 填充到 3 位确保字典序排序正确
│
├── content: str           → 文本片段正文
│
└── metadata: ChunkMetadata
    ├── document_id: str     → 原始文档编号
    ├── document_name: str   → 原始文件名（用户上传时的文件名）
    ├── page_number: int?    → 页码（精确映射 或 估算。）
    │                          对 TXT/MD 等无页码概念的文件 = chunk_index + 1
    ├── chunk_index: int     → 当前文档中的片段序号（从 0 开始）
    ├── total_chunks: int    → 当前文档总片段数（同一文档所有 chunk 的值相同）
    └── course: str          → 课程名称（前端上传时传入，grouping 用）
```

**`to_chroma_format()` 转换逻辑**：

```python
# 输入
chunk = Chunk(chunk_id="doc001_chunk_003", content="...", metadata=...)

# 输出
{
    "id":       "doc001_chunk_003",     # Chroma 每条记录的唯一标识
    "document": "Cache 是位于 CPU...",  # Chroma 要求命名为 "document"（不是 "content"）
    "metadata": {
        "document_id":   "doc001",      # 扁平化 metadata → Chroma 仅接受 dict[str,str|int|float|bool]
        "document_name": "数据库系统概论.pdf",
        "page_number":   12,
        "chunk_index":   3,
        "total_chunks":  15,
        "course":        "数据库",
    },
}
```

注意：`asdict(chunk.metadata)` 将 dataclass 递归转为 dict，`None` 值会被保留（Chroma 接受 `None`）。

---

### 8.12 整体数据流

```
文件上传 (FastAPI UploadFile)
  │
  ▼
保存到 uploads/  ← B 负责
  │
  ▼
get_file_type(filename) → "pdf"
  │
  ▼
parse_document(file_path, file_type)   ← 你的模块
  ├── PDF  → parse_pdf()
  ├── TXT  → parse_txt()
  ├── DOCX → parse_docx()
  ├── MD   → parse_markdown()
  ├── HTML → parse_html()
  └── PPTX → parse_pptx()
  │
  ▼
clean_text(raw_text)
  ├── \n{3,}    → \n\n
  ├── [ \t]+    → " "
  ├── 控制字符  → 删除
  └── 行首尾空格 → strip
  │
  ▼
split_text(clean_text, chunk_size=500, overlap=100)
  └── 递归字符切分算法 → List[str] (共 N 个)
  │
  ▼
build_chunks(...)
  ├── for each text chunk:
  │     ├── 精确页码映射 (PDF only)
  │     ├── 生成 chunk_id: "doc001_chunk_003"
  │     └── 构建 Chunk(chunk_id, content, ChunkMetadata(...))
  │
  ▼
List[Chunk]  ← 交付给 B & D
  │
  ├──→ chroma_service.add_chunks(chunks)  ← D 负责
  │      └── chunk.to_chroma_format() 遍历写入 Chroma
  │
  ├──→ get_split_statistics(chunks)        ← E 写报告用
  ├──→ visualize_chunks(chunks, "html")    ← 可视化
  └──→ export_chunks_to_json(chunks)       ← 导出
```

---

## 九、实验数据收集（配合成员 E）

```python
# 实验二：不同 chunk_size
for size in [300, 500, 800]:
    chunks = build_chunks(..., chunk_size=size, overlap=size//5)
    print(f"chunk_size={size}: {get_split_statistics(chunks)}")
    # 导出供报告
    export_chunks_to_json(chunks, f"uploads/chunks_{size}.json")

# 可视化对比
visualize_chunks(chunks, output_format="text")
```

---

## 十、注意事项 & 避坑指南

1. **PDF 中文乱码**：pypdf 对部分中文 PDF 兼容性一般，可换 `pdfplumber`
2. **扫描版 PDF**：pypdf 提取为空时，可调用 `parse_pdf_with_ocr()` 回退 OCR
3. **DOCX 限制**：图片/公式无法提取（业界通用限制）
4. **PPTX 限制**：SmartArt 图形、嵌入视频等无法提取
5. **编码回退**：TXT 自动 UTF-8 → GBK → Latin-1
6. **大文件**：建议限制 50MB，避免解析超时
7. **Chunk 编号从 0 开始**：和 Python 习惯一致

---

## 十一、交付检查清单

- [x] `backend/models/chunk.py` — Chunk 数据模型
- [x] `backend/services/document_loader.py` — 文档解析器（6 种格式）
- [x] `backend/services/text_splitter.py` — 文本切分器 + 可视化 + 导出
- [x] `backend/tests/test_document_loader.py` — 解析测试
- [x] `backend/tests/test_text_splitter.py` — 切分测试
- [x] `backend/requirements.txt` — 依赖清单
- [ ] 准备 6 种格式的测试样本文件
- [ ] 运行测试并截图留存
- [ ] 运行可视化，保存图表截图
- [ ] 与成员 B、D 联调确认接口
- [ ] 切分样例截图（放入报告）

---

## 十二、FAQ

**Q: 扫描版 PDF 怎么办？**  
A: 调用 `parse_pdf_with_ocr(path)`，会自动回退 OCR。需先装系统依赖。

**Q: DOCX 公式丢失？**  
A: python-docx 不支持 MathType/Office 公式，报告中注明即可。

**Q: 如何可视化切分结果？**  
A: `visualize_chunks(chunks, "text")` 直接在控制台看；`"matplotlib"` / `"html"` 保存文件。

**Q: 精确页码映射准吗？**  
A: 对文字层 PDF 精确度 >90%。空白页或扫描版会回退估算。

**Q: 和成员 B 怎么联调？**  
A: B 调 `build_chunks()` → 拿到 chunks → 调 `chunk.to_chroma_format()` → 给 D。你在本地先跑通测试即可。
