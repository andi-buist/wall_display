import json
import datetime
from pathlib import Path

def localcache_write(filepath: str, id: str, timestamp: float, value: any, hr_limit: int = None):
    if Path(filepath).is_file():
        with open(filepath) as json_data:
            history = json.load(json_data)
            json_data.close()
    else:
        history = {}
    
    earliest_date = datetime.datetime.now() - datetime.timedelta(hours = hr_limit)

    if id in history.keys():
        new_hist = history[id]
        new_hist[timestamp] = value

        #remove old keys
        if hr_limit:
            to_del = []
            for key in new_hist.keys():
                if float(key) < earliest_date.timestamp(): to_del.append(key)
            
            for key in to_del:
                new_hist.pop(key)
    else:
        new_hist = {timestamp: value}
    
    history[id] = new_hist
    
    with open(filepath, 'w') as file_write:
            json.dump(history, file_write)
            file_write.close()
    
def localcache_read(filepath: str, id: str = None):
    if Path(filepath).is_file():
        with open(filepath) as json_data:
            history = json.load(json_data)
            json_data.close()

        if id:
            if id in history.keys():
                return history[id]
            else:
                return {}
        else:
            return history
    else:
        return {}