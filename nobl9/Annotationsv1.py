#!/usr/bin/env python3

# This script will create an annotation in the SLO based on current time plus 5 min. You can modify that below.  

from enum import Enum
from datetime import datetime, timedelta
import sys
import json
from unicodedata import name
import requests
import rfc3339

URL = "https://app.nobl9.com"
ORGANIZATION = "your_org_name_here"

#Grab this from your SLO CTL file. 
CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"

#Go get a token. 
#TODO use configparse to pull the token from a config file and check to see if valid. If so keep going, If not refresh. 

TOKEN = requests.post(
        f"{URL}/api/accessToken",
        auth=(CLIENT_ID, CLIENT_SECRET),
        headers={"organization": ORGANIZATION},
    )
if TOKEN.status_code == 200:
    print("We have a Token")
else:
    print("Somthing is Broken")
    print(TOKEN.text)
    exit(1)


TOKEN = TOKEN.json()["access_token"]


# Tell me the Project and SLO you want to put an annotation on, and the Annotation Name

PROJECT = "Name of your project"
SLO_NAME = "The name of your SLO (real name not display name)"
ANNOTATION_NAME = "The Name of your annotation"
ANNOTATION_DATA = "Blurb of Text for your annotation"

# Set Annotation time period. If you want to set a particular time, comment out line 48 and 49 and go to line 52 to set your specific time. 

now = datetime.utcnow()
since = now + timedelta(minutes=5) #  5 mimutes, change the minutes= to something longer if you like.

# RFC 3339 timestamp. Nobl9 needs this.
# Set varibles. If you want a specific time use this format. 
# FROM = "2021-11-25T14:10:00.000Z"
# TO = "2021-12-25T14:10:00.000Z"

# Uncomment these to use the auto set time from now to plus what ever you set above. (line 49)
FROM = rfc3339.rfc3339(since)
TO = rfc3339.rfc3339(now)

SLO_ANNOTATION = {'slo' : SLO_NAME, 'project' : PROJECT, 'name' : ANNOTATION_NAME, 'description' : ANNOTATION_DATA, 'startTime' : TO, 'endTime' : FROM}

# Add the annotation.

print("Creating Annotation")

r = requests.post(
    f"{URL}/api/annotations",
    data=json.dumps(SLO_ANNOTATION),
    headers={
        "authorization": f"Bearer {TOKEN}",
        "organization": ORGANIZATION,
    },
)
if r.status_code == 200:
    print("SLO Annotation created")
else:
    print("SLO Annotation not created")
    print(r.text)
    exit(1)
