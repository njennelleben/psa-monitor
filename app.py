import threading
import time
import requests
import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask

app = Flask(__name__)

# --- Your monitor logic ---
def monitor():
    scraper = cloudscraper.create_scraper()

    while True:
        print("Checking PSA prices...")

        try:
            # replace with your original fetch logic
            url = "https://your-psa-url.com"
            html = scraper.get(url).text
            soup = BeautifulSoup(html, "html.parser")

            # example parsing:
            price = soup.select_one(".price").text

            # send to webhook
            requests.post(
                "WEBHOOK_URL_HERE",
                json={"text": f"Current price: {price}"}
            )

        except Exception as e:
            print("Error:", e)

        time.sleep(60)


# Start background thread
threading.Thread(target=monitor, daemon=True).start()


# --- Required route for Pella ---
@app.route("/")
def home():
    return "PSA Monitor Running"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
