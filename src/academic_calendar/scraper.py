from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import traceback
from datetime import datetime, timedelta
from src.supabase_utils import supabase
from selenium.webdriver.chrome.service import Service as ChromeService
from src.slack_utils import Slack_Notifier

class AcademicCalendarScraper:
    def __init__(self, driver_path):
        self.base_url = 'https://www.gnu.ac.kr/main/ps/schdul/selectSchdulMainList.do?mi='
        self.driver_path = driver_path
        self.driver = None

    def __enter__(self):
        options = Options()
        options.add_argument("headless")
        service = ChromeService(self.driver_path)
        self.driver = webdriver.Chrome(service=service, options=options)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.driver:
            self.driver.quit()

    def scrape_academic_calendar_data(self):
        try:
            with self as scraper:
                scraper.driver.get(self.base_url)
                scraper.driver.implicitly_wait(10)
                parsed_html = BeautifulSoup(scraper.driver.page_source, 'html.parser')

                tbody_element = parsed_html.find('tbody')
                a_elements = tbody_element.find_all('a')

                result = []
                for a_element in a_elements:
                    # href 속성에서 날짜 정보를 추출
                    onclick_value = a_element['href']
                    start_date = datetime.strptime(onclick_value.split("'")[3], '%Y/%m/%d')
                    end_date = datetime.strptime(onclick_value.split("'")[5], '%Y/%m/%d')

                    if end_date < datetime.now() - timedelta(days=1):
                        continue

                    # 텍스트에서 '2학기 동계방학' 추출
                    contents = a_element.get_text()
                    # 카테고리 추출
                    category_idx = contents.find('-')
                    category = contents[1:category_idx]
                    content_idx = contents.find(']')
                    if content_idx != -1:
                        content = contents[content_idx + 1:].strip()
                    else:
                        continue

                    schedule_object = {
                        'calendar_type': 1 if category == '학부' else 2,
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                        'content': content
                    }
                    result.append(schedule_object)

                self.delete_schedules()
                self.insert_schedules(result)
                print('[학사일정] 학사일정 데이터 교체 완료')

        except Exception as e:
            print(f'[학사일정] 학사일정 데이터 조회 실패: 학사일정 데이터를 {e}의 사유로 가져오는데 실패했습니다.')
            print(f'[학사일정] 해당 학사일정 url: {self.base_url}')
            Slack_Notifier().fail(f'학사일정 데이터 조회 실패: 학사일정 데이터를 {e}의 사유로 가져오는데 실패했습니다. \n \
                                    해당 학사일정 url: {self.base_url}')
            traceback.print_exc()

    def insert_schedules(self, schedules):
        supabase().table('academic_calendar').insert(schedules).execute()

    def delete_schedules(self):
        supabase().table('academic_calendar').delete().neq('content', 0).execute()
