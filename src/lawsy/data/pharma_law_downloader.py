#!/usr/bin/env python3
"""
薬事関連法令XMLダウンロード機能

e-Gov法令APIから薬事関連法令を選択的にダウンロードする
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class PharmaLawDownloader:
    """薬事関連法令のダウンロードクラス"""

    # 薬事関連法令の法令番号とメタデータ
    PHARMA_LAWS = {
        "yakki_law": {
            "law_id": "335AC0000000145",  # 昭和35年法律第145号
            "title": "医薬品、医療機器等の品質、有効性及び安全性の確保等に関する法律",
            "short_name": "薬機法",
            "category": "law",
        },
        "gmp_ordinance": {
            "law_id": "416M60000100179",  # 平成16年厚生労働省令第179号
            "title": "医薬品及び医薬部外品の製造管理及び品質管理の基準に関する省令",
            "short_name": "GMP省令",
            "category": "ordinance",
        },
        "gcp_ordinance": {
            "law_id": "409M50000100028",  # 平成9年厚生省令第28号
            "title": "医薬品の臨床試験の実施の基準に関する省令",
            "short_name": "GCP省令",
            "category": "ordinance",
        },
        "gvp_ordinance": {
            "law_id": "416M60000100135",  # 平成16年厚生労働省令第135号
            "title": "医薬品、医薬部外品、化粧品、医療機器及び再生医療等製品の製造販売後安全管理の基準に関する省令",
            "short_name": "GVP省令",
            "category": "ordinance",
        },
        "gpsp_ordinance": {
            "law_id": "416M60000100171",  # 平成16年厚生労働省令第171号
            "title": "医薬品の製造販売後の調査及び試験の実施の基準に関する省令",
            "short_name": "GPSP省令",
            "category": "ordinance",
        },
    }

    def __init__(self, output_dir: str = "./data/pharma_xml", timeout: int = 30):
        self.output_dir = Path(output_dir)
        self.timeout = timeout
        self.base_url = "https://laws.e-gov.go.jp/api/1"

        # 出力ディレクトリを作成
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # HTTPセッションの設定（リトライ機能付き）
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # ログファイルパス
        self.log_file = self.output_dir / "download_log.json"
        self.download_log = self._load_log()

    def _load_log(self) -> Dict:
        """ダウンロードログを読み込み"""
        if self.log_file.exists():
            with open(self.log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"downloads": [], "last_update": None}

    def _save_log(self):
        """ダウンロードログを保存"""
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.download_log, f, ensure_ascii=False, indent=2)

    def _download_law_xml(self, law_id: str, law_info: Dict) -> Tuple[bool, Optional[str]]:
        """
        指定された法令IDのXMLをダウンロード

        Returns:
            Tuple[bool, Optional[str]]: (成功フラグ, エラーメッセージ)
        """
        try:
            # API URLを構築
            url = f"{self.base_url}/lawdata/{law_id}"

            print(f"ダウンロード中: {law_info['short_name']} ({law_id})")
            print(f"URL: {url}")

            # API呼び出し
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            # レスポンスがXMLかチェック
            content_type = response.headers.get("content-type", "").lower()
            if "xml" not in content_type:
                return False, f"XMLではないレスポンス: {content_type}"

            # ファイル名を生成
            filename = f"{law_info['short_name']}_{law_id}.xml"
            safe_filename = filename.replace("/", "_").replace("\\", "_")
            file_path = self.output_dir / safe_filename

            # XMLファイルを保存
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(response.text)

            # ダウンロード情報をログに記録
            download_info = {
                "law_id": law_id,
                "title": law_info["title"],
                "short_name": law_info["short_name"],
                "category": law_info["category"],
                "filename": safe_filename,
                "file_path": str(file_path),
                "download_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "file_size": len(response.text),
                "status": "success",
            }

            self.download_log["downloads"].append(download_info)
            self.download_log["last_update"] = download_info["download_time"]

            print(f"✓ 保存完了: {file_path}")
            return True, None

        except requests.exceptions.RequestException as e:
            error_msg = f"HTTP エラー: {str(e)}"
            print(f"✗ エラー: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"予期しないエラー: {str(e)}"
            print(f"✗ エラー: {error_msg}")
            return False, error_msg

    def download_all_pharma_laws(self, delay: float = 1.0) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        全ての薬事関連法令をダウンロード

        Args:
            delay: リクエスト間隔（秒）

        Returns:
            Dict[str, Tuple[bool, Optional[str]]]: 各法令のダウンロード結果
        """
        print("=== 薬事関連法令XMLダウンロード開始 ===")
        print(f"出力ディレクトリ: {self.output_dir}")
        print(f"対象法令数: {len(self.PHARMA_LAWS)}")
        print()

        results = {}

        for law_key, law_info in self.PHARMA_LAWS.items():
            success, error = self._download_law_xml(law_info["law_id"], law_info)
            results[law_key] = (success, error)

            if not success:
                # エラー情報をログに記録
                error_info = {
                    "law_id": law_info["law_id"],
                    "short_name": law_info["short_name"],
                    "download_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "error",
                    "error_message": error,
                }
                self.download_log["downloads"].append(error_info)

            # ログを保存
            self._save_log()

            # API負荷軽減のため待機
            if delay > 0:
                time.sleep(delay)

        print()
        print("=== ダウンロード完了 ===")

        # 結果サマリーを表示
        success_count = sum(1 for success, _ in results.values() if success)
        total_count = len(results)

        print(f"成功: {success_count}/{total_count}")

        if success_count < total_count:
            print("エラー:")
            for law_key, (success, error) in results.items():
                if not success:
                    law_info = self.PHARMA_LAWS[law_key]
                    print(f"  - {law_info['short_name']}: {error}")

        return results

    def download_specific_law(self, law_key: str) -> Tuple[bool, Optional[str]]:
        """
        特定の法令をダウンロード

        Args:
            law_key: 法令キー（PHARMA_LAWSのキー）

        Returns:
            Tuple[bool, Optional[str]]: (成功フラグ, エラーメッセージ)
        """
        if law_key not in self.PHARMA_LAWS:
            return False, f"未知の法令キー: {law_key}"

        law_info = self.PHARMA_LAWS[law_key]
        success, error = self._download_law_xml(law_info["law_id"], law_info)

        # ログを保存
        self._save_log()

        return success, error

    def get_download_status(self) -> Dict:
        """ダウンロード状況を取得"""
        downloaded_laws = set()
        for download_info in self.download_log["downloads"]:
            if download_info.get("status") == "success":
                # law_idから法令キーを逆引き
                for law_key, law_info in self.PHARMA_LAWS.items():
                    if law_info["law_id"] == download_info["law_id"]:
                        downloaded_laws.add(law_key)
                        break

        return {
            "total_laws": len(self.PHARMA_LAWS),
            "downloaded_count": len(downloaded_laws),
            "downloaded_laws": list(downloaded_laws),
            "missing_laws": [k for k in self.PHARMA_LAWS.keys() if k not in downloaded_laws],
            "last_update": self.download_log.get("last_update"),
            "output_directory": str(self.output_dir),
        }

    def list_available_laws(self) -> List[Dict]:
        """利用可能な薬事関連法令リストを取得"""
        return [
            {
                "key": key,
                "law_id": info["law_id"],
                "title": info["title"],
                "short_name": info["short_name"],
                "category": info["category"],
            }
            for key, info in self.PHARMA_LAWS.items()
        ]


def main():
    """メイン実行関数"""
    import argparse

    parser = argparse.ArgumentParser(description="薬事関連法令XMLダウンロード")
    parser.add_argument(
        "--output-dir", "-o", default="./data/pharma_xml", help="出力ディレクトリ (default: ./data/pharma_xml)"
    )
    parser.add_argument("--delay", "-d", type=float, default=1.0, help="リクエスト間隔（秒） (default: 1.0)")
    parser.add_argument("--law", "-l", type=str, help="特定の法令のみダウンロード（法令キーを指定）")
    parser.add_argument("--list", action="store_true", help="利用可能な法令リストを表示")
    parser.add_argument("--status", action="store_true", help="ダウンロード状況を表示")

    args = parser.parse_args()

    downloader = PharmaLawDownloader(output_dir=args.output_dir)

    if args.list:
        print("=== 利用可能な薬事関連法令 ===")
        for law in downloader.list_available_laws():
            print(f"キー: {law['key']}")
            print(f"  名前: {law['short_name']}")
            print(f"  正式名称: {law['title']}")
            print(f"  法令ID: {law['law_id']}")
            print(f"  カテゴリ: {law['category']}")
            print()
        return

    if args.status:
        status = downloader.get_download_status()
        print("=== ダウンロード状況 ===")
        print(f"対象法令数: {status['total_laws']}")
        print(f"ダウンロード済み: {status['downloaded_count']}")
        print(f"出力ディレクトリ: {status['output_directory']}")
        if status["last_update"]:
            print(f"最終更新: {status['last_update']}")

        if status["downloaded_laws"]:
            print(f"ダウンロード済み法令: {', '.join(status['downloaded_laws'])}")

        if status["missing_laws"]:
            print(f"未ダウンロード法令: {', '.join(status['missing_laws'])}")
        return

    if args.law:
        # 特定の法令をダウンロード
        success, error = downloader.download_specific_law(args.law)
        if success:
            print(f"✓ {args.law} のダウンロードが完了しました")
        else:
            print(f"✗ {args.law} のダウンロードに失敗しました: {error}")
    else:
        # 全ての薬事関連法令をダウンロード
        results = downloader.download_all_pharma_laws(delay=args.delay)


if __name__ == "__main__":
    main()
