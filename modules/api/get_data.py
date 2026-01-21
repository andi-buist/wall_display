# TODO: move this to readme eventually
# many of these get_xxx() functions have equivalents with similar names in widget modules, like map.py.
# the way I tried to define the separation between the two is that get_data.py get_xxx() functions should 
# return as much raw-ish data as possible from the API under minimal constraints, producing `something`
# widget get_xxx() functions should ingest `something` and further manipulate it to make data ingestible for UI
# functions. e.g. Strava data is tricky and requires several API calls. rather than wrap the Client in multiple
# match-case statements, I just return the initiated Client after auth. then, the widget get_strava() function can
# figure out what it wants. e.g.:
# get_data.get_strava_client() -> `Client` -> map.get_strava_data(args) -> `data` -> map.plt_strava_data() -> END
# similar logic should go for everything :)

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
from stravalib.model import DetailedActivity
from pathlib import Path
import polyline
import contextlib
import sys

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

def get_strava_data(period: tuple[datetime.datetime, datetime.datetime] = (datetime.datetime.today() - datetime.timedelta(days = 30), datetime.datetime.now()), cache_frequency: datetime.timedelta = datetime.timedelta(hours = 1), cache_filepath: Path = Path("./data/strava_data_cache.json")) -> dict:
    # strava oauth is a pain

    # process goes:
    # A1: manually do client.authorization_url(), get code from URL bar after auth
    # A2: client.exchange_code(code) -> access_token, refresh_token, expirations
    # The above steps are pretty manual. If someone else is reading this, good luck? follow strava docs/above and then add refresh_token to tokens.json and you'll be fine
    # B1: every time we call client.refresh_access_token(refresh_token), we get a new access_token and (if expired) new refresh_token(!!!)
    # B2: (!!!) this then needs to be saved as the new refresh token
    # and the B loop restarts 
    client = stravalib.Client()

    with contextlib.redirect_stdout(None) and contextlib.redirect_stderr(None):
        init_response = client.refresh_access_token(
            client_id=token_config['strava_config']['client_id'],
            client_secret=token_config['strava_config']['client_secret'],
            refresh_token=token_config['strava_config']['refresh_token']
        )

    # write new refresh token, restart token loop
    token_config['strava_config']['refresh_token'] = init_response['refresh_token']
    with open("tokens.json", "w") as f:
        f.write(json.dumps(token_config, indent=4))

    # get cached data if within time constraint, else gen new and save
    if cache_filepath.is_file():
        with open(cache_filepath) as json_data:
            last_cache = json.load(json_data)
            json_data.close()
    else:
        last_cache = {"datetime": False}
        
    if not last_cache["datetime"] or (datetime.datetime.now() - datetime.datetime.fromtimestamp(last_cache["datetime"])) > cache_frequency:
        # no cache or cache is old, fetch new data
        client.access_token = init_response['access_token']
        activities = client.get_activities(after = period[0], before = period[1])

        detailed_activities: list[DetailedActivity] = []
        for activity in activities:
            detailed_activity = client.get_activity(activity.id)
            detailed_activities.append(detailed_activity)

        data = {"type": None, "datetime": datetime.datetime.now().timestamp(), "data": {}}
        for detailed_activity in detailed_activities:
            activity_dict = {}
            activity_dict["start_date"] = detailed_activity.start_date.timestamp()
            activity_dict["distance"] = detailed_activity.distance
            activity_dict["polyline"] = [(x[1],x[0]) for x in polyline.polyline.decode(detailed_activity.map.polyline)] # need to flip to lon_lat
            activity_dict["start_point"] = tuple(reversed(detailed_activity.start_latlng.root))
            activity_dict["end_point"] = tuple(reversed(detailed_activity.end_latlng.root))
            activity_dict["calories"] = detailed_activity.calories
            activity_dict["average_heartrate"] = detailed_activity.average_heartrate
            activity_dict["achievements"] = {}
            for effort in detailed_activity.segment_efforts:
                achievements: list[dict] = []
                for achievement in effort.achievements:
                    achievements.append({"rank": achievement.rank, "type": achievement.type})
                activity_dict["achievements"][effort.id] = {"name": effort.name, "achievements": achievements}
            

            data['data'][str(detailed_activity.id)] = activity_dict
        
        with open(cache_filepath, 'w') as file_write:
            json.dump(data, file_write, indent=4)
            file_write.close()
    else:
        data = last_cache

    return data

def nostdout():
    save_stdout = sys.stdout
    sys.stdout = BytesIO()
    yield
    sys.stdout = save_stdout