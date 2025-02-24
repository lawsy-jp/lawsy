import xml.etree.ElementTree as ET
from pathlib import Path

from ja_law_parser.model import Law
from ja_law_parser.parser import LawParser


def parse_from_api_response(xml_content: str) -> Law:
    parser = LawParser()
    # ja_law_parserはXMLフォーマットに準拠しており、Lawタグ配下を取り出して与える必要がある。
    tree = ET.fromstring(xml_content)
    node = tree.find(".//Law")
    assert node is not None
    parsed = parser.parse_from(ET.tostring(node))
    return parsed


def parse_from_xml_file(xml_file: Path | str) -> Law:
    parser = LawParser()
    parsed = parser.parse(xml_file)
    return parsed
