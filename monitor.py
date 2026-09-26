import os
import smtplib
import schedule
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# This monitor is intentionally limited to the single product requested by the owner.
PRODUCT_URL = "https://www.amazon.co.jp/gp/product/B07D9PNSLB"


class AmazonStockMonitor:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.email = os.getenv("EMAIL")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.check_interval = int(os.getenv("CHECK_INTERVAL", "30"))
        self.previous_state = None

        if not self.email or not self.email_password:
            raise ValueError("EMAIL と EMAIL_PASSWORD を .env に設定してください")

    def fetch_product_info(self):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
        }
        response = requests.get(PRODUCT_URL, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        title_element = soup.select_one("#productTitle")
        title = title_element.get_text(" ", strip=True) if title_element else "Amazon商品"
        availability = soup.select_one("#availability")
        availability_text = availability.get_text(" ", strip=True) if availability else ""
        page_text = soup.get_text(" ", strip=True).lower()

        # Prefer Amazon's availability area. The page-wide fallback supports
        # common Amazon Japan stock text but may need adjustment if Amazon changes HTML.
        in_stock = any(
            text.lower() in availability_text.lower()
            for text in ("在庫あり", "通常1～2か月以内に発送", "通常 1～2 か月以内に発送")
        )
        if not availability_text:
            in_stock = any(text in page_text for text in ("在庫あり", "in stock"))

        return title, in_stock, availability_text

    def send_email(self, title, availability_text):
        message = MIMEMultipart()
        message["From"] = self.email
        # Send only to the same address configured as the sender.
        message["To"] = self.email
        message["Subject"] = f"Amazon入荷通知: {title}"
        message.attach(
            MIMEText(
                f"商品が入荷した可能性があります。\n\n"
                f"商品: {title}\n"
                f"在庫表示: {availability_text or '在庫あり'}\n"
                f"URL: {PRODUCT_URL}\n"
                f"確認日時: {datetime.now():%Y-%m-%d %H:%M:%S}\n",
                "plain",
                "utf-8",
            )
        )

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.starttls()
            server.login(self.email, self.email_password)
            server.send_message(message)

    def check_product(self):
        try:
            title, in_stock, availability_text = self.fetch_product_info()
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {title}: in_stock={in_stock}")

            # Do not notify on the initial check; notify only on a later
            # transition from out of stock to in stock.
            if self.previous_state is False and in_stock:
                self.send_email(title, availability_text)
                print("入荷通知メールを送信しました")
            self.previous_state = in_stock
        except Exception as error:
            print(f"監視に失敗しました: {error}")

    def start(self):
        print(f"監視対象: {PRODUCT_URL}")
        print(f"チェック間隔: {self.check_interval}分")
        self.check_product()
        schedule.every(self.check_interval).minutes.do(self.check_product)

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("監視を停止しました")


if __name__ == "__main__":
    AmazonStockMonitor().start()
