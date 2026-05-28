import requests
import xml.etree.ElementTree as ET
url = "https://news.google.com/rss/search?q=US+China&hl=en-US&gl=US&ceid=US:en"
resp = requests.get(url)
root = ET.fromstring(resp.text)
item = root.find(".//item")
print("Title:", item.find("title").text)
if item.find("pubDate") is not None:
    print("PubDate:", item.find("pubDate").text)
else:
    print("No pubDate found!")
