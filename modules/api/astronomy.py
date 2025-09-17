import base64
import datetime
import pandas as pd
import requests

def get_astro_data(lon_lat: tuple, api_id: str, api_secret:str, timestamp: str = None):
    userpass = api_id + ":" + api_secret
    authString = base64.b64encode(userpass.encode()).decode()

    if timestamp is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    else:
        dt = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")

    response = requests.get("https://api.astronomyapi.com/api/v2/bodies/positions/",
                 headers = {"Authorization": "Basic " + authString},
                 params = {"longitude": str(lon_lat[0]),
                           "latitude": str(lon_lat[1]),
                           "elevation": str(0),
                           "from_date": dt.date(),
                           "to_date": dt.date(),
                           "time": dt.strftime("%H:%M:%S")
                           }).json()

    return [x[0] for x in pd.DataFrame.from_dict(response['data']['table']['rows'])['cells']]