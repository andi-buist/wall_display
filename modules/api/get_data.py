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

#TODO: token
def get_strava_data(period: tuple[datetime.datetime, datetime.datetime] = (datetime.datetime.today() - datetime.timedelta(days = 30), datetime.datetime.now()), 
                    cache_frequency: datetime.timedelta = datetime.timedelta(hours = 1), 
                    cache_filepath: Path = Path("./data/strava_data_cache.json")) -> dict:
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