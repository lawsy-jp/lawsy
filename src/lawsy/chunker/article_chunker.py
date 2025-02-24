from typing import Iterable

from ja_law_parser.model import (
    Article,
    Chapter,
    Division,
    Item,
    # Subitem1,
    # Subitem2,
    # Subitem3,
    # Subitem4,
    # Subitem5,
    # Subitem6,
    # Subitem7,
    # Subitem8,
    # Subitem9,
    # Subitem10,
    Law,
    LawBody,
    MainProvision,
    Paragraph,
    # EnactStatement,
    # Preamble,
    Part,
    Section,
    Subsection,
    SupplProvision,
)

from lawsy.utils.logging import get_logger


def list_article_paths(law: Law) -> list[list]:
    next_children_names = {
        Law: ["law_body"],
        LawBody: ["enact_statement", "preamble", "main_provision", "suppl_provisions"],
        MainProvision: ["parts", "chapters", "sections", "articles", "paragraphs"],
        SupplProvision: ["chapters", "articles", "paragraphs"],
        Part: ["chapters", "articles"],
        Chapter: ["sections", "articles"],
        Section: ["sub_sections", "divisions", "articles"],
        Subsection: ["divisions", "articles"],
        Division: ["articles"],
        Article: ["paragraphs"],
        Paragraph: ["items"],
        Item: ["subitems"],
        # Subitem1: ["subitems2"],
        # Subitem2: ["subitems3"],
        # Subitem3: ["subitems4"],
        # Subitem4: ["subitems5"],
        # Subitem5: ["subitems6"],
        # Subitem6: ["subitems7"],
        # Subitem7: ["subitems8"],
        # Subitem8: ["subitems9"],
        # Subitem9: ["subitems10"],
    }

    def dfs(node, found_article_paths: list[list], cur_path: list):
        new_path = cur_path + [node]
        if type(node) is Article:
            found_article_paths.append(new_path)
            return
        if type(node) not in next_children_names:
            return
        if type(node) is SupplProvision and getattr(node, "amend_law_num", None) is not None:
            # 改正法制番号付きの場合は無視
            # https://laws.e-gov.go.jp/docs/law-data-basic/8ebd8bc-law-structure-and-xml/#%E3%81%9D%E3%81%AE1%E6%9C%AC%E5%89%87%E3%82%84%E9%99%84%E5%89%87%E3%81%AA%E3%81%A9
            return
        children_names = next_children_names[type(node)]
        for name in children_names:
            child_or_children = getattr(node, name, None)
            if not child_or_children:
                continue
            if isinstance(child_or_children, list):
                for child in child_or_children:
                    dfs(child, found_article_paths, new_path)
            else:
                dfs(child_or_children, found_article_paths, new_path)
        return

    found_articles = []
    cur_path = []
    dfs(law, found_articles, cur_path)
    return found_articles


def get_item_text(item: Item, indent=2) -> str:
    texts = []
    for sentence in item.item_sentence.sentences or []:
        texts.append(sentence.text)
    for column in item.item_sentence.columns or []:
        if column.sentences:
            for sentence in column.sentences:
                texts.append(sentence.text)
    if item.item_title and item.item_title.text:  # type: ignore
        return str(item.item_title.text) + ". " + "  ".join(texts)  # type: ignore
    else:
        return "  ".join(texts)


def get_paragraph_text(paragraph: Paragraph, indent=2) -> str:
    texts = []
    if paragraph.paragraph_caption:
        texts.append(paragraph.paragraph_caption.text)  # type: ignore
    if paragraph.paragraph_sentence:
        if paragraph.paragraph_sentence.sentences:
            for sentence in paragraph.paragraph_sentence.sentences:
                texts.append(sentence.text)
    for item in paragraph.items or []:
        item_text = get_item_text(item)
        texts.extend([" " * (indent + 1) + line for line in item_text.split("\n")])
    return "\n".join(texts)


def get_article_text(article: Article, indent=2) -> str:
    lines = []
    if article.article_caption:
        lines.append(article.article_title.text + " " + article.article_caption.text)  # type: ignore
    else:
        lines.append(article.article_title.text)  # type: ignore
    for paragraph in article.paragraphs:
        paragraph_text = get_paragraph_text(paragraph, indent=indent)
        for line in paragraph_text.split("\n"):
            lines.append(line)
    return "\n".join(lines)


def get_article_path_string(article_path: list, start_node_type=LawBody, indent=2) -> str:
    start = [type(node) for node in article_path].index(start_node_type)
    article_path = article_path[start:]
    texts = []
    for i, node in enumerate(article_path):
        if type(node) is LawBody:
            texts.append(" " * indent * i + node.law_title.text)  # type: ignore
        elif type(node) is MainProvision:
            texts.append(" " * indent * i + "本則")
        elif type(node) is SupplProvision:
            texts.append(" " * indent * i + "附則")
        elif type(node) in [Part, Chapter, Section, Subsection, Division]:
            texts.append(" " * indent * i + getattr(node, node.__class__.__name__.lower() + "_title").text)
        elif type(node) is Article:
            article_text = get_article_text(node, indent=indent)
            texts.extend([" " * indent * i + line for line in article_text.split("\n")])
    text = "\n".join(texts)
    return text


class ArticleChunker:
    def __init__(self, indent: int = 2):
        self.indent = indent

    @staticmethod
    def get_article_path_anchor(article_path: list) -> str:
        """
        Mp-Pa_2-Ch_8-Se_2-Ss_3-At_327-Pr_1のような、法令ページで使用されているようなアンカー（フラグメント）を取得する
        """
        symbols = []
        for node in article_path:
            if type(node) is MainProvision:
                symbols.append("Mp")
            elif type(node) is SupplProvision:
                symbols.append("Sp")
            elif type(node) is Part:
                symbols.append("Pa_" + node.num)
            elif type(node) is Chapter:
                symbols.append("Ch_" + node.num)
            elif type(node) is Section:
                symbols.append("Se_" + node.num)
            elif type(node) is Subsection:
                symbols.append("Ss_" + node.num)
            elif type(node) is Division:
                symbols.append("Di_" + node.num)
            elif type(node) is Article:
                symbols.append("At_" + node.num)
            elif type(node) is Paragraph:
                symbols.append("Pr_" + str(node.num))
            elif type(node) is Item:
                symbols.append("It_" + node.num)
        return "-".join(symbols)

    def __call__(self, law: Law) -> Iterable[dict]:
        article_paths = list_article_paths(law)
        for article_path in article_paths:
            anchor = self.get_article_path_anchor(article_path)
            try:
                yield {
                    "anchor": anchor,
                    "article_path": article_path,
                    "chunk": get_article_path_string(article_path, indent=self.indent),
                }
            except Exception:
                import traceback

                logger = get_logger()
                logger.warning(f"cannot create chunk ({anchor})")
                logger.warning(traceback.format_exc())
