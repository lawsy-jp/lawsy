import datetime
import json
import time
from pathlib import Path

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt
from tqdm import tqdm


@retry(stop=stop_after_attempt(5))
def get_json(url):
    res = requests.get(url)
    res.raise_for_status()
    return res.json()


def crawl_monthly_mtgs(month: datetime.date) -> list:
    from_date = month.strftime("%Y-%m-%d")
    if month.month == 12:
        until_date = (datetime.date(month.year + 1, 1, 1) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        until_date = (datetime.date(month.year, month.month + 1, 1) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    next_record_position = 1
    mtgs = []
    while next_record_position:
        url = f"https://kokkai.ndl.go.jp/api/meeting_list?recordPacking=json&from={from_date}&until={until_date}&startRecord={next_record_position}"
        mtg_list_data = get_json(url)
        if "meetingRecord" not in mtg_list_data:  # no issues
            break
        for mtg_data in mtg_list_data["meetingRecord"]:
            issue_id = mtg_data["issueID"]
            url2 = f"https://kokkai.ndl.go.jp/api/meeting?recordPacking=json&issueID={issue_id}"
            detailed_mtg_data = get_json(url2)
            if "meetingRecord" not in detailed_mtg_data:
                logger.warning(
                    f"meetingRecord key does not exist in detailed_mtg_data (from: {from_date}, until: {until_date}"
                )
            else:
                mtgs.append(detailed_mtg_data["meetingRecord"][0])
            time.sleep(0.2)
        next_record_position = mtg_list_data["nextRecordPosition"]
    return mtgs


def main(output_path: Path, from_year: int = 1945, until_year: int = 2025):
    assert from_year <= until_year
    existing_months = set()
    existing_issue_ids = set()
    existing_speech_ids = set()
    if output_path.exists():
        logger.info("loading existing data...")
        with open(output_path) as fin:
            for line in fin:
                d = json.loads(line)
                year, month, day = d["date"].split("-")
                existing_months.add((int(year), int(month)))
                existing_issue_ids.add(d["issueID"])
                for dd in d["speechRecord"]:
                    existing_speech_ids.add(dd["speechID"])
        logger.info("existing speeches: {}", len(existing_speech_ids))
        logger.info("existing issues: {}", len(existing_issue_ids))
        min_existing_month = min(existing_months)
        max_existing_month = max(existing_months)
        logger.info(
            "existing year/month: {} (from: {}, until: {})",
            len(existing_months),
            min_existing_month,
            max_existing_month,
        )
    else:
        min_existing_month = None
        max_existing_month = None

    target_year_months = []
    today = datetime.date.today()
    for year in range(from_year, until_year + 1):
        for month in range(1, 13):
            # データがあるのは1947年5月以降
            if (year, month) < (1947, 5):
                continue
            # 指定期間内。ただし最終月は取得時点の可能性があるので補完
            if (min_existing_month is None or (min_existing_month <= (year, month))) and (
                max_existing_month is None or ((year, month) < max_existing_month)
            ):
                continue
            # 現時点まで
            if today < datetime.date(year, month, 1):
                continue
            target_year_months.append((year, month))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bar = tqdm(total=len(target_year_months))
    bar.set_description("crawling")
    add_count = 0
    with open(output_path, "a") as fout:
        for year, month in target_year_months:
            bar.set_description(f"Processing {year}-{month}")
            mtgs = crawl_monthly_mtgs(datetime.date(year, month, 1))
            for d in mtgs:
                if d["issueID"] not in existing_issue_ids:
                    print(json.dumps(d, ensure_ascii=False), file=fout)
                    add_count += 1
            bar.update(1)
    bar.close()
    logger.info(f"added new {add_count} issues")


if __name__ == "__main__":
    import typer

    typer.run(main)
