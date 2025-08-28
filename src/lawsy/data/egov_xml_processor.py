#!/usr/bin/env python3
"""
e-Gov API XMLファイルの前処理

e-Gov APIから取得したXMLファイルをja_law_parserで処理可能な形式に変換する
"""

import json
from pathlib import Path
from typing import List
import xml.etree.ElementTree as ET


class EgovXmlProcessor:
    """e-Gov API XMLファイルの前処理クラス"""

    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 処理ログ
        self.processed_files = []
        self.error_files = []

    def extract_law_xml(self, input_file: Path) -> tuple[bool, str]:
        """
        e-Gov APIのXMLファイルからLaw要素を抽出

        Args:
            input_file: 入力XMLファイルパス

        Returns:
            tuple[bool, str]: (成功フラグ, エラーメッセージまたは出力ファイルパス)
        """
        try:
            # XMLファイルを読み込み
            tree = ET.parse(input_file)
            root = tree.getroot()

            # DataRoot > ApplData > LawFullText > Law の構造を確認
            if root.tag != "DataRoot":
                return False, f"Expected DataRoot, got {root.tag}"

            # ApplData要素を探す
            appl_data = root.find("ApplData")
            if appl_data is None:
                return False, "ApplData element not found"

            # LawFullText要素を探す
            law_full_text = appl_data.find("LawFullText")
            if law_full_text is None:
                return False, "LawFullText element not found"

            # Law要素を探す
            law_element = law_full_text.find("Law")
            if law_element is None:
                return False, "Law element not found"

            # 出力ファイル名を生成
            output_filename = input_file.stem + "_processed.xml"
            output_file = self.output_dir / output_filename

            # Law要素のみを含む新しいXMLを作成
            # XML宣言を含める
            xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
            law_xml = ET.tostring(law_element, encoding="unicode", xml_declaration=False)

            # ファイルに保存
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(xml_declaration)
                f.write(law_xml)

            # 処理成功をログに記録
            self.processed_files.append(
                {
                    "input_file": str(input_file),
                    "output_file": str(output_file),
                    "law_id": appl_data.find("LawId").text if appl_data.find("LawId") is not None else "unknown",
                }
            )

            return True, str(output_file)

        except ET.ParseError as e:
            error_msg = f"XML parse error: {str(e)}"
            self.error_files.append({"input_file": str(input_file), "error": error_msg})
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.error_files.append({"input_file": str(input_file), "error": error_msg})
            return False, error_msg

    def process_all_files(self) -> dict:
        """
        入力ディレクトリ内の全XMLファイルを処理

        Returns:
            dict: 処理結果サマリー
        """
        print(f"=== e-Gov XML前処理開始 ===")
        print(f"入力ディレクトリ: {self.input_dir}")
        print(f"出力ディレクトリ: {self.output_dir}")

        # XMLファイルを検索
        xml_files = list(self.input_dir.glob("*.xml"))
        if not xml_files:
            print("XMLファイルが見つかりません")
            return {"total": 0, "success": 0, "error": 0}

        print(f"対象ファイル数: {len(xml_files)}")
        print()

        success_count = 0
        error_count = 0

        for xml_file in xml_files:
            print(f"処理中: {xml_file.name}")
            success, result = self.extract_law_xml(xml_file)

            if success:
                print(f"✓ 処理完了: {Path(result).name}")
                success_count += 1
            else:
                print(f"✗ エラー: {result}")
                error_count += 1
            print()

        print("=== 前処理完了 ===")
        print(f"成功: {success_count}")
        print(f"エラー: {error_count}")

        # 処理ログを保存
        log_file = self.output_dir / "processing_log.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "processed_files": self.processed_files,
                    "error_files": self.error_files,
                    "summary": {"total": len(xml_files), "success": success_count, "error": error_count},
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return {
            "total": len(xml_files),
            "success": success_count,
            "error": error_count,
            "processed_files": self.processed_files,
            "error_files": self.error_files,
        }

    def get_processed_files(self) -> List[Path]:
        """処理済みファイルのパスリストを取得"""
        return [Path(file_info["output_file"]) for file_info in self.processed_files]


def main():
    """メイン実行関数"""
    import argparse

    parser = argparse.ArgumentParser(description="e-Gov API XMLファイルの前処理")
    parser.add_argument("input_dir", help="入力ディレクトリ")
    parser.add_argument("output_dir", help="出力ディレクトリ")

    args = parser.parse_args()

    processor = EgovXmlProcessor(args.input_dir, args.output_dir)
    result = processor.process_all_files()

    if result["error"] > 0:
        print("\nエラーが発生したファイル:")
        for error_file in result["error_files"]:
            print(f"  - {error_file['input_file']}: {error_file['error']}")

    return 0 if result["error"] == 0 else 1


if __name__ == "__main__":
    exit(main())
