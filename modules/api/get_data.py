import base64
import datetime
import pandas as pd
import requests_cache
import config
from urllib.parse import quote
from PIL import Image, ImageFilter
from io import BytesIO
import xarray as xr
import tempfile
import os
import numpy as np

astro_session = requests_cache.CachedSession('.cache/astro/cached_requests', expire_after=60)
met_office_session = requests_cache.CachedSession('.cache/met_office/cached_requests', expire_after=3600)

def get_astro_data(lon_lat: tuple, timestamp: str = None) -> list:
    userpass = config.astronomy_config['id'] + ":" + config.astronomy_config['secret']
    authString = base64.b64encode(userpass.encode()).decode()

    if timestamp is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    else:
        dt = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")

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

    return [x[0] for x in pd.DataFrame.from_dict(response['data']['table']['rows'])['cells']]

def get_met_office_grib(file_id: str = None) -> dict:
    safe_file_id = quote(file_id + str(datetime.datetime.now().hour), safe="")

    api_key = config.met_office_atmospheric_models_config['secret']
    api_url = f"https://data.hub.api.metoffice.gov.uk/atmospheric-models/1.0.0/orders/{config.met_office_atmospheric_models_config['order_id']}/latest/{safe_file_id}/data"

    response = met_office_session.get(api_url,
                 headers = {
                     "apikey": api_key,
                     "Accept": "*/*"
                     })

    tmp_path = os.path.join(tempfile.gettempdir(), f"{safe_file_id}.grib2") # Write GRIB bytes to disk 
    with open(tmp_path, "wb") as f: 
        f.write(response.content)

    # get grib2 -> xarray
    data = xr.open_dataset(tmp_path, engine="cfgrib")
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

# deprecated in favour of grib with known range
def get_met_office_map_overlay(file_id: str = None) -> dict:
    safe_file_id = quote(file_id + str(datetime.datetime.now().hour) +"_+00", safe="")

    api_key = config.met_office_map_images_config['secret']
    api_url = f"https://data.hub.api.metoffice.gov.uk/map-images/1.0.0/orders/{config.met_office_map_images_config['order_id']}/latest/{safe_file_id}/data"

    response = met_office_session.get(api_url,
                 headers = {
                     "apikey": api_key,
                     "Accept": "image/png"
                     })
    
    image = Image.open(BytesIO(response.content)).convert('RGBA')

    return {"image": image, "timestamp": response.created_at}