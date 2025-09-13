import json
import datetime

global global_entity_cache
global_entity_cache = {}

def entity_cache_write(entity_id: str, key: str, value):
    """Assigns the specified value to the key of an entity_id dictionary in the global_entity_cache."""
    if entity_id in global_entity_cache.keys():
        global_entity_cache[entity_id][key] = value
    else:
        global_entity_cache[entity_id] = {key: value}

def entity_cache_read(entity_id: str, key: str, fallback):
    """Gets the value of the specified key from the entity_id dictionary of the global_entity_cache. If there's nothing there, it returns fallback."""
    #pull cached value if exists
    if entity_id in global_entity_cache.keys() and key in global_entity_cache[entity_id]:
        return global_entity_cache[entity_id][key]
    else:
        return fallback

def localcache_write(filepath: str, id: str, timestamp: datetime.datetime, value: any, hr_limit: int = None):
    with open(filepath) as json_data:
        history = json.load(json_data)
        json_data.close()
    
    earliest_date = datetime.datetime.now() - datetime.timedelta(hours = hr_limit)

    if id in history.keys():
        new_hist = history[id]
        new_hist[timestamp] = value

        #remove old keys
        if hr_limit:
            to_del = []
            for key in new_hist.keys():
                if datetime.datetime.strptime(key, "%Y-%m-%dT%H:%M:%S.%fZ") < earliest_date: to_del.append(key)
            
            for key in to_del:
                new_hist.pop(key)
    else:
        new_hist = {timestamp: value}
    
    history[id] = new_hist
    
    with open(filepath, 'w') as file_write:
            json.dump(history, file_write)
            file_write.close()
    
def localcache_read(filepath: str, id: str):
    with open(filepath) as json_data:
        history = json.load(json_data)
        json_data.close()

    if id in history.keys():
        return history[id]
    else:
        return {}