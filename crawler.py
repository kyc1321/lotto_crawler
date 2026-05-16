"""
동행복권 로또 645 당첨번호 크롤러
https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do에서 당첨번호를 크롤링합니다.
"""

import argparse
import csv
import json
from pathlib import Path
import requests
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class LottoCrawler:
    def __init__(self):
        self.base_url = "https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def fetch_lottery_results(self, draw_number: int) -> Optional[Dict]:
        """
        로또 당첨번호를 크롤링합니다.

        Args:
            draw_number: 조회할 회차 번호

        Returns:
            당첨번호 정보를 담은 딕셔너리
        """
        try:
            params = {
                'srchDir': 'center',
                'srchLtEpsd': draw_number,
                '_': int(time.time() * 1000),
            }
            response = requests.get(self.base_url, headers=self.headers, params=params)
            response.raise_for_status()

            data = response.json()
            result = self._parse_lottery_result(data, draw_number)
            return result
            
        except requests.RequestException as e:
            print(f"요청 오류: {e}")
            return None
        except Exception as e:
            print(f"파싱 오류: {e}")
            return None

    def _parse_lottery_result(self, data: dict, draw_number: int) -> Optional[Dict]:
        """
        JSON 응답에서 당첨번호를 파싱합니다.
        """
        try:
            if not data or 'data' not in data:
                return None
            results = data['data'].get('list', [])
            if not results:
                return None

            item = next((row for row in results if row.get('ltEpsd') == draw_number), None)
            if item is None:
                return None

            winning_numbers = [
                item.get('tm1WnNo'),
                item.get('tm2WnNo'),
                item.get('tm3WnNo'),
                item.get('tm4WnNo'),
                item.get('tm5WnNo'),
                item.get('tm6WnNo'),
            ]
            winning_numbers = [num for num in winning_numbers if isinstance(num, int)]

            draw_date = item.get('ltRflYmd')
            if isinstance(draw_date, str) and len(draw_date) == 8:
                draw_date = f"{draw_date[:4]}.{draw_date[4:6]}.{draw_date[6:8]}"

            return {
                'round': item.get('ltEpsd'),
                'winning_numbers': sorted(winning_numbers),
                'bonus_number': item.get('bnsWnNo'),
                'draw_date': draw_date,
            }
        except Exception as e:
            print(f"파싱 중 오류 발생: {e}")
            return None

    @staticmethod
    def load_results(filepath: str) -> List[Dict]:
        """CSV 파일을 읽어서 JSON 딕셔너리로 변환합니다."""
        path = Path(filepath)
        if not path.exists():
            return []

        try:
            with path.open('r', encoding='utf-8') as f:
                reader = csv.DictReader(f, fieldnames=['round', 'draw_date', 'no1', 'no2', 'no3', 'no4', 'no5', 'no6', 'bonus'])
                results = []
                for row in reader:
                    try:
                        results.append({
                            'round': int(row['round']),
                            'draw_date': row['draw_date'],
                            'winning_numbers': [
                                int(row['no1']),
                                int(row['no2']),
                                int(row['no3']),
                                int(row['no4']),
                                int(row['no5']),
                                int(row['no6']),
                            ],
                            'bonus_number': int(row['bonus']),
                        })
                    except (ValueError, KeyError):
                        continue
            return results
        except (OSError, UnicodeDecodeError):
            pass
        return []

    @staticmethod
    def save_results(filepath: str, results: List[Dict]) -> None:
        """JSON 딕셔너리를 CSV 형식으로 저장합니다."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with path.open('w', encoding='utf-8', newline='') as f:
            fieldnames = ['round', 'date', 'no1', 'no2', 'no3', 'no4', 'no5', 'no6', 'bonus']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                if isinstance(result.get('round'), int) and isinstance(result.get('winning_numbers'), list):
                    nums = result['winning_numbers']
                    writer.writerow({
                        'round': result['round'],
                        'date': result['draw_date'],
                        'no1': nums[0] if len(nums) > 0 else '',
                        'no2': nums[1] if len(nums) > 1 else '',
                        'no3': nums[2] if len(nums) > 2 else '',
                        'no4': nums[3] if len(nums) > 3 else '',
                        'no5': nums[4] if len(nums) > 4 else '',
                        'no6': nums[5] if len(nums) > 5 else '',
                        'bonus': result.get('bonus_number', ''),
                    })

    @staticmethod
    def merge_results(existing: List[Dict], new_results: List[Dict]) -> List[Dict]:
        merged = {item['round']: item for item in existing if isinstance(item.get('round'), int)}
        for item in new_results:
            if isinstance(item.get('round'), int):
                merged[item['round']] = item
        return sorted(merged.values(), key=lambda x: x['round'], reverse=False)

    def crawl_from_file(self, output_file: str, start_draw: Optional[int] = None) -> int:
        existing = self.load_results(output_file)
        if existing:
            latest_round = max((item.get('round') for item in existing if isinstance(item.get('round'), int)), default=0)
            latest_date = max((item.get('draw_date') for item in existing if item.get('round') == latest_round), default='')
            start = latest_round + 1
        else:
            if start_draw is None:
                raise ValueError('결과 파일이 없을 경우 --start를 지정해야 합니다.')
            start = start_draw
            latest_date = ''

        # print(f"latest_round:{latest_round}, latest_date:{latest_date}")

        if start_draw is not None:
            start = max(start, start_draw)
            if latest_date != '':
                next_date = datetime.strptime(latest_date, '%Y.%m.%d') + timedelta(days=7)
            else:
                next_date = datetime.strptime('1900.01.01', '%Y.%m.%d')

        crawled = []
        current = start
        maxRetry = 40
        today = datetime.now()
        has_next = next_date <= today

        # 마지막 조회결과의 추첨일이 오늘인 경우 정지(추첨데이터 없음)
        while has_next and maxRetry > 0:
            print(f"retrying drawNum: {current}, remain: {maxRetry}, next_date:{next_date.strftime('%Y.%m.%d')}")
            maxRetry = maxRetry - 1
            result = self.fetch_lottery_results(current)
            if result is None:
                if maxRetry > 0:
                    time.sleep(5 * 60)
                    continue
                break

            crawled.append(result)
            next_date = datetime.strptime(result['draw_date'], '%Y.%m.%d') + timedelta(days=7)
            has_next = next_date <= today
            if has_next:
                current += 1
                maxRetry = 40
            
        if crawled:
            merged = self.merge_results(existing, crawled)
            self.save_results(output_file, merged)

        return len(crawled)


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="로또 645 당첨번호 크롤러")
    parser.add_argument(
        "--output",
        "-o",
        default="lotto_results.csv",
        help="결과 CSV 파일 경로",
    )
    parser.add_argument(
        "--start",
        type=int,
        help="출력 파일이 없을 경우 시작 회차",
    )
    parser.add_argument(
        "--single",
        type=int,
        help="단일 회차 조회",
    )
    args = parser.parse_args()

    crawler = LottoCrawler()

    if args.single is not None:
        print(f"{args.single}회차 로또 645 당첨번호를 가져오고 있습니다...")
        result = crawler.fetch_lottery_results(args.single)
        if result:
            print("\n======" * 1)
            print(f"회차: {result['round']}회")
            print(f"당첨번호: {', '.join(map(str, result['winning_numbers']))}")
            print(f"보너스번호: {result['bonus_number']}")
            print(f"추첨일: {result['draw_date']}")
            print("======" * 1)
        else:
            print("당첨번호를 가져올 수 없습니다.")
        return

    try:
        crawled = crawler.crawl_from_file(args.output, args.start)
        if crawled:
            print(f"{crawled}개 회차를 {args.output}에 저장했습니다.")
        else:
            print("새로운 회차 데이터가 없습니다.")
    except ValueError as e:
        print(e)


if __name__ == "__main__":
    main()
