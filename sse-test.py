import requests 
import json


def connect_sse(url, event_reception_callback):
    r = requests.get(url, stream=True)

    if r.encoding is None:
        r.encoding = 'utf-8'

    s = ""

    curr_event = None

    for line in r.iter_lines(decode_unicode=True):
        if line == "" and curr_event:
            event_reception_callback(curr_event)

        if line:
            line_parsed = line.split(":")
            if len(line_parsed) >= 2:
                k, v = line.split(":")[0], ":".join(line.split(":")[1:])
                
                if k == "event":
                    curr_event = {}

                if k == "data":
                    v = json.loads(v)
                else:
                    v = v.strip()

                curr_event[k.strip()] = v


def _test(payload):
    print(payload)


connect_sse("https://piquetdestream-api.fly.dev/v1/counter/sse", _test)