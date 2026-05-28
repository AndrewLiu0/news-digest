import requests

def test_gdelt_raw():
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query":      '(near20:"United States China" OR near20:"US China") (domain:fmprc.gov.cn)',
        "timespan":   "3d",
        "format":     "json",
    }
    resp = requests.get(url, params=params)
    print(f"Status Code: {resp.status_code}")
    print(f"Response Text: {resp.text}")

if __name__ == "__main__":
    test_gdelt_raw()
