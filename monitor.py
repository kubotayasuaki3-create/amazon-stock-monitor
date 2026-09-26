import os
import smtplib
import schedule
import time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()

class AmazonStockMonitor:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        self.product_urls = [url.strip() for url in os.getenv('PRODUCT_URLS', '').split(',')]
        self.check_interval = int(os.getenv('CHECK_INTERVAL', 30))
        
        # Store previous states to detect changes
        self.product_states = {}
        
    def fetch_product_info(self, url):
        """Fetch product information from Amazon URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to get product title
            title_elem = soup.find('span', {'id': 'productTitle'})
            title = title_elem.get_text(strip=True) if title_elem else 'Unknown Product'
            
            # Check if in stock (basic check - may need adjustment for different pages)
            in_stock = self._check_availability(soup)
            
            return {
                'title': title,
                'in_stock': in_stock,
                'url': url,
                'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            print(f"Error fetching product info from {url}: {str(e)}")
            return {
                'title': 'Error fetching product',
                'in_stock': False,
                'url': url,
                'error': str(e),
                'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def _check_availability(self, soup):
        """Check if product is in stock"""
        # Look for common Amazon Japan in-stock indicators
        in_stock_text = ['在庫あり', 'In stock', 'すぐに購入できます']
        
        # Check various elements that might contain stock status
        stock_elements = soup.find_all(['span', 'div', 'a'], {'class': lambda x: x and any(
            keyword in x.lower() for keyword in ['availability', 'stock', 'in-stock']
        )})
        
        page_text = soup.get_text().lower()
        
        for keyword in in_stock_text:
            if keyword.lower() in page_text:
                return True
        
        return False
    
    def send_email(self, subject, body):
        """Send email notification"""
        try:
            message = MIMEMultipart()
            message['From'] = self.sender_email
            message['To'] = self.recipient_email
            message['Subject'] = subject
            
            message.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            print(f"Email sent successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            print(f"Error sending email: {str(e)}")
    
    def check_products(self):
        """Check all products and send notifications if stock status changes"""
        print(f"\n{'='*50}")
        print(f"Checking products at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        for url in self.product_urls:
            product_info = self.fetch_product_info(url)
            current_state = product_info['in_stock']
            
            # Check if state changed
            if url in self.product_states:
                previous_state = self.product_states[url]
                
                if previous_state != current_state and current_state:
                    # Stock status changed from unavailable to available
                    subject = f"✅ In Stock! {product_info['title']}"
                    body = f"""
Product: {product_info['title']}
Status: NOW IN STOCK!
URL: {url}
Checked at: {product_info['checked_at']}

Click the link above to purchase!
                    """
                    self.send_email(subject, body)
                    print(f"✅ Stock available for: {product_info['title']}")
            
            self.product_states[url] = current_state
            print(f"Product: {product_info['title'][:60]}...")
            print(f"In Stock: {current_state}")
    
    def start(self):
        """Start the monitoring scheduler"""
        print("Amazon Stock Monitor Started!")
        print(f"Check interval: {self.check_interval} minutes")
        print(f"Products to monitor: {len(self.product_urls)}")
        
        # Schedule the check
        schedule.every(self.check_interval).minutes.do(self.check_products)
        
        # Run initial check
        self.check_products()
        
        # Keep scheduler running
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nMonitor stopped by user")

if __name__ == '__main__':
    monitor = AmazonStockMonitor()
    monitor.start()
