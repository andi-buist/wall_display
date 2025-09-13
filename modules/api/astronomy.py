import base64
import datetime
import pandas as pd
import requests

def get_astro_data(lat_lon: tuple, api_id: str, api_secret:str, timestamp: str = None):
    userpass = api_id + ":" + api_secret
    authString = base64.b64encode(userpass.encode()).decode()

    if timestamp is None:
        dt = datetime.datetime.now()
    else:
        dt = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")

    return [x[0] for x in pd.DataFrame.from_dict(requests.get("https://api.astronomyapi.com/api/v2/bodies/positions/",
                 headers = {"Authorization": "Basic " + authString},
                 params = {"latitude": str(lat_lon[0]),
                           "longitude": str(lat_lon[1]),
                           "elevation": str(0),
                           "from_date": dt.date(),
                           "to_date": dt.date(),
                           "time": dt.strftime("%H:%M:%S")
                           }).json()['data']['table']['rows'])['cells']]