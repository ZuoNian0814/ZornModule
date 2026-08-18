from markdown_it import MarkdownIt
import json, re

def parse_markdown_bold(text: str) -> list[tuple[str, bool]]:
    """
    解析Markdown中**包裹的粗体内容，按顺序返回(文本, 是否为粗体)列表
    正确识别**的开始/结束标记，处理所有边界场景
    """
    # 核心正则：非贪婪匹配**包裹的内容，捕获组保留匹配结果
    pattern = r'(\*\*.*?\*\*)'
    # 分割文本，保留分隔符（粗体片段）
    parts = re.split(pattern, text)
    result = []

    for part in parts:
        # 跳过空字符串（可选，根据需求决定是否保留）
        if not part:
            continue
        # 判断是否是**包裹的粗体内容
        if part.startswith('**') and part.endswith('**'):
            # 去掉**，标记为粗体
            bold_content = part.strip('*')
            result.append((bold_content, True))
        else:
            # 普通文本
            result.append((part, False))

    return result

def parse_markdown(md_content):
    # 初始化解析器
    md = MarkdownIt()
    # 解析为语法令牌
    tokens = md.parse(md_content)

    # 自定义处理：将令牌转为结构化字典
    structure = []
    for token in tokens:
        # 标题
        if token.type == "heading_open":
            level = int(token.tag[1])
            content = tokens[tokens.index(token)+1].content
            structure.append({"type": "heading", "level": level, "content": content})
        # 普通段落
        elif token.type == "paragraph_open":
            content = tokens[tokens.index(token)+1].content
            structure.append({"type": "paragraph", "content": content})
        # 代码块
        elif token.type == "fence":
            structure.append({
                "type": "code_block",
                "language": token.info,
                "content": token.content.strip()
            })
        # 引用
        elif token.type == "blockquote_open":
            structure.append({"type": "quote", "content": "引用文本"})

    # 转为格式化 JSON
    # json_result = json.dumps(structure, ensure_ascii=False, indent=2)
    return structure

def _get_display_width(text: str) -> int:
    """
    计算文本的显示宽度：中文=2字符，英文/数字/符号/Markdown标记=1字符
    """
    width = 0
    for char in text:
        # 判断是否为中文字符（Unicode 基本汉字范围）
        if '\u4e00' <= char <= '\u9fff':
            width += 2
        else:
            width += 1
    return width

def format_markdown_table(table_str: str) -> str:
    """
    将Markdown表格转换为【右侧对齐、中英文宽度计算、移除分隔线】的格式化字符串
    :param table_str: 原始Markdown表格字符串
    :return: 格式化后的表格字符串
    """
    # 1. 分割行 + 去除首尾空格 + 过滤空行
    lines = [line.strip() for line in table_str.split('\n') if line.strip()]

    # 2. 过滤：移除包含分隔线（-----）的行
    valid_lines = [line for line in lines if '-----' not in line]

    if not valid_lines:
        return ""

    # 3. 解析每一行的单元格（按|分割，去除空单元格）
    table_cells = []
    for line in valid_lines:
        # 分割单元格 + 去除每个单元格首尾空格 + 过滤空字符串
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        table_cells.append(cells)

    # 校验：所有行列数一致
    col_count = len(table_cells[0])
    for cells in table_cells:
        if len(cells) != col_count:
            raise ValueError("表格格式错误：各行列数不一致")

    # 4. 计算每一列的【最大显示宽度】
    max_col_widths = []
    for col_idx in range(col_count):
        # 取出当前列所有单元格的文本
        col_texts = [row[col_idx] for row in table_cells]
        # 计算每个单元格的显示宽度，取最大值
        max_width = max(_get_display_width(text) for text in col_texts)
        max_col_widths.append(max_width)

    # 5. 格式化每一行：右侧对齐 + 按最大宽度填充
    formatted_lines = []
    for row_cells in table_cells:
        formatted_cells = []
        for idx, cell in enumerate(row_cells):
            # 目标宽度
            target_w = max_col_widths[idx]
            # 当前宽度
            current_w = _get_display_width(cell)
            # 计算需要填充的空格数（右侧对齐，空格补在左侧）
            pad_space = target_w - current_w
            # 拼接：空格 + 单元格内容
            formatted_cell = ' ' * pad_space + cell
            formatted_cells.append(formatted_cell)
        # 拼接成行：| 单元格 | 单元格 |
        formatted_line = '| ' + ' | '.join(formatted_cells) + ' |'
        formatted_lines.append(formatted_line)

    # 6. 拼接所有行，返回结果
    return '\n'.join(formatted_lines)