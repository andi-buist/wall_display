import json
import base64
import datetime
import pandas as pd
import requests
import requests_cache
import time
from urllib.parse import quote
from PIL import Image
from io import BytesIO
import xarray as xr
import os
import numpy as np
import stravalib

with open("tokens.json") as f: 
    token_config = json.load(f)

astro_session = requests_cache.CachedSession('.cache/astro/cached_requests', expire_after=60)
met_office_session = requests_cache.CachedSession('.cache/met_office/cached_requests', expire_after=3600)

def get_astro_data(lon_lat: tuple, timestamp: str = None, retries: int = 5) -> list:
    userpass = token_config['astronomy_config']['id'] + ":" + token_config['astronomy_config']['secret']
    authString = base64.b64encode(userpass.encode()).decode()

    if timestamp is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    else:
        dt = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")

    for attempt in range(retries):
        try:
            response = astro_session.get("https://api.astronomyapi.com/api/v2/bodies/positions/",
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
            break
        except requests.exceptions.ConnectionError:
            time.sleep(2 ** attempt)

    return [x[0] for x in pd.DataFrame.from_dict(response['data']['table']['rows'])['cells']]

def get_met_office_grib(file_id: str = None, retries: int = 5) -> dict:
    safe_file_id = quote(file_id + str(datetime.datetime.now().hour), safe="")

    api_key = token_config['met_office_atmospheric_models_config']['secret']
    api_url = f"https://data.hub.api.metoffice.gov.uk/atmospheric-models/1.0.0/orders/{token_config['met_office_atmospheric_models_config']['order_id']}/latest/{safe_file_id}/data"

    for attempt in range(retries):
        try:
            response = met_office_session.get(api_url,
                    headers = {
                        "apikey": api_key,
                        "Accept": "*/*"
                        })
            break
        except requests.exceptions.ConnectionError:
            time.sleep(2 ** attempt)

    raw_path =".cache/met_office/grib_bytes_tmp.grib2"
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, "wb") as f:
        f.write(response.content)

    data = xr.open_dataset(raw_path,
                           engine="cfgrib",
                           backend_kwargs={"indexpath": ""}) # prevent idx file gen
    # find name of primary data key
    primary_key = list(data.data_vars.keys())[0]

    # get values as array
    values = np.flip(data[primary_key].values,0)
    # get range
    value_range = (values.min(), values.max())

    # normalise
    values = (((values - values.min())/(values.max() - values.min()))*255).astype(np.uint8)

    image = Image.fromarray(values)

    return {"image": image, "value_range": value_range, "timestamp": response.created_at}

def get_strava_data():
    
    client = stravalib.Client()

    activities = client.get_activities(after = (datetime.datetime.today() - datetime.timedelta(days = 7)))
    data = list(activities)
    return data
