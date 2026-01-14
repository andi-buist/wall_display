import base64
import datetime
import pandas as pd
import requests_cache
import config
from urllib.parse import quote
from PIL import Image 
from io import BytesIO

session = requests_cache.CachedSession('cached_requests')

def get_astro_data(lon_lat: tuple, timestamp: str = None) -> list:
    userpass = config.astronomy_config['id'] + ":" + config.astronomy_config['secret']
    authString = base64.b64encode(userpass.encode()).decode()

    if timestamp is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    else:
        dt = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")

    response = session.get("https://api.astronomyapi.com/api/v2/bodies/positions/",
                 headers = {
                     "Authorization": "Basic " + authString
                     },
                 params = {
                     "longitude": str(lon_lat[0]),
                           "latitude": str(lon_lat[1]),
                           "elevation": str(0),
                           "from_date": dt.date(),
                           "to_date": dt.date(),
                           "time": dt.strftime("%H:%M:%S")
                           }).json()

    return [x[0] for x in pd.DataFrame.from_dict(response['data']['table']['rows'])['cells']]

def get_met_office_map_overlay(file_id: str = None) -> Image.Image:

    cache_path = str(datetime.datetime.now().replace(minute=0, second=0, microsecond=0))

    safe_file_id = quote(file_id, safe="")

    api_key = config.met_office_weatherhub_config['secret']
    api_url = f"https://data.hub.api.metoffice.gov.uk/map-images/1.0.0/orders/{config.met_office_weatherhub_config['order_id']}/latest/{safe_file_id}/data"

    response = session.get(api_url,
                 headers = {
                     "apikey": api_key,
                     "Accept": "image/png"
                     })
    
    image = Image.open(BytesIO(response.content))

    return image