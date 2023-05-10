#!/usr/bin/env python3

from enum import Enum
from datetime import datetime, timedelta
import configparser
import sys
import json
import requests
import rfc3339

# Fill these out with your ORG ID, a Project Name (not display name) and a SLO Name 
URL = "https://app.nobl9.com"
ORGANIZATION = "software"
PROJECT = "software-slo"
SLO_NAME = "prod-latency"

#Grab this from your SLO CTL file. 
CLIENT_ID = "YOURclienIdHERE"
CLIENT_SECRET = "YOURclientSecretHERE"


# Go get an access token for the API.
# Need to clean this up later to test first then if bad go get a new one.


TOKEN = requests.post(
        f"{URL}/api/accessToken",
        auth=(CLIENT_ID, CLIENT_SECRET),
        headers={"organization": ORGANIZATION},
    )
if TOKEN.status_code == 200:
    print("We have a token")
else:
    print("We didn't get a token")
    print(TOKEN.text)
    exit(1)


TOKEN = TOKEN.json()["access_token"]

# SeriesEnum helper for providing predefined time series types.
class SeriesEnum(str, Enum):
    percentiles = "percentiles"
    counts = "counts"
    instantaneousBurnRate = "instantaneousBurnRate"
    burnDown = "burnDown"

    def __str__(self) -> str:
        return self.value

# SeriesPercentilesLevel helper for providing predefined percentiles levels.
class SeriesPercentilesLevel(str, Enum):
    p1 = "p1"
    p5 = "p5"
    p10 = "p10"
    p50 = "p50"
    p90 = "p90"
    p95 = "p95"
    p99 = "p99"

    def __str__(self) -> str:
        return self.value


now = datetime.utcnow()
since = now - timedelta(hours=3) # Last 3 hours.

# RFC 3339 timestamp.
# FROM = "2021-11-25T14:10:00.000Z"
# TO = "2021-12-25T14:10:00.000Z"
FROM = rfc3339.rfc3339(since)
TO = rfc3339.rfc3339(now)

STEPS = 20  # [1, 1000] - inclusive range - how many points to return for given time period (for series=percentiles IS TREATED ONLY AS A HINT).

# Possible values for param
# series=
# - percentiles - for raw metrics (threshold), additional parameter - q possible values p1, p5, p10, p50, p90, p95, p99 e.g. q=p99 (when omitted all series are returned) - paremeter steps= treated only as hint returned number of points ma differ.
# - counts      - for ratio type SLO (good & total are returned)
# - instantaneousBurnRate
# - burnDown
SERIES = SeriesEnum.instantaneousBurnRate

Q = SeriesPercentilesLevel.p95  # It's not taken into account if series is different than percentiles and when ommited all percentiles are returned.

r = requests.get(
    f"{URL}/api/timeseries/slo",
    params={ # URL params
        "name": SLO_NAME,
        "from": FROM,
        "to": TO,
        "steps": STEPS,
        "series": SERIES,
        "q": Q, # Comment to ommit and get all percentiles for series percentiles.
    },
    headers={
        "authorization": f"Bearer {TOKEN}",
        "organization": ORGANIZATION,
        "project": PROJECT,
    },
)

# Use these to see what your output is
#print(r.status_code)
#print(r.url)
#print(r.text)

#Pretty Pint the JSON, put it in an object. 

json_data = r.text
json_object = json.loads(json_data)
json_formatted_str = json.dumps(json_object, indent = 2)
print(json_formatted_str)

#check for errors
error_budget_remaining_percentage = 0
try:
    error_budget_remaining_percentage = json_object[0]['timewindows'][0]['objectives'][0]['status']['errorBudgetRemainingPercentage']
except KeyError as ke:
    print('Data was not available from Nobl9 for this SLO; please check your SLO %s in project %s' % (SLO_NAME, PROJECT))
    print(repr(ke))
    print('proceed with release anyway')
    sys.exit(0)
except Exception as e:
    print('Something has gone wrong fetching data from Nobl9')
    print(repr(e))
    print('proceed with release anyway')
    sys.exit(0)

#make a go, or no go decision. 

pretty_eb = error_budget_remaining_percentage * 100
print('Error budget remaining is %2.2f%%' % pretty_eb)
if error_budget_remaining_percentage > 0:
    print("prodeed with release")
    sys.exit(0)
else:
    print("cancel release")
    sys.exit(1)