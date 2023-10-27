import base64
import requests
from requests_oauthlib import OAuth2Session
from lambdas.utils.utils import get_secret, get_with_paginate_helper
import boto3
import csv
import json
import time
from datetime import datetime, timedelta

MYJOHNDEERE_V3_JSON_HEADERS = {'Accept': 'application/vnd.deere.axiom.v3+json',
                               'Content-Type': 'application/vnd.deere.axiom.v3+json'}
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def lambda_handler(event, context):
    deere_app_secret = '/insightsdsc/api/jdeerai/apidetails'
    deere_app_creds = get_secret(deere_app_secret)

    CLIENT_ID = deere_app_creds['client_id']
    CLIENT_SECRET = deere_app_creds['client_secret']
    CLIENT_REDIRECT_URI = deere_app_creds['client_redirect_uri']

    WELL_KNOWN_URL = 'https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/.well-known/oauth-authorization-server'

    # Query the ./well-known OAuth URL and parse out the authorization URL, the token grant URL, and the available scopes
    well_known_response = requests.get(WELL_KNOWN_URL)
    well_known_info = json.loads(well_known_response.text)

    TOKEN_GRANT_URL = well_known_info['token_endpoint']
    AVAILABLE_SCOPES = str(' ').join(well_known_info['scopes_supported'])

    print('Well Known Token Grant URL - ' + TOKEN_GRANT_URL)
    print('Available Scopes - ' + AVAILABLE_SCOPES)

    SCOPES_TO_REQUEST = {'offline_access', 'ag1', 'eq1', 'files'}
    oauth2_session = OAuth2Session(CLIENT_ID, redirect_uri=CLIENT_REDIRECT_URI, scope=SCOPES_TO_REQUEST)

    REFRESH_TOKEN = deere_app_creds['refresh_token']
    token_response = oauth2_session.refresh_token(TOKEN_GRANT_URL, refresh_token=REFRESH_TOKEN,
                                                  auth=(CLIENT_ID, CLIENT_SECRET))

    s3 = boto3.resource('s3', region_name='us-east-2')

    bucket_name = 'insightsdsc-use2-sandbox-shared-glue-resources'
    org_file_path = 'data/john-deere/organizations.csv'

    bucket = s3.Bucket(bucket_name)
    org_obj = bucket.Object(key=org_file_path)
    response = org_obj.get()
    lines = response['Body'].read().decode('utf-8').splitlines(True)

    reader = csv.DictReader(lines)
    rows = []
    for row in reader:
        rows.append(row)

    organization_ids = [org['id'] for org in rows]

    # Getting Machines
    all_machines = []
    embed_request_param = {'embed': 'terminals,breadcrumbs,categories,capabilities,displays'}

    for org_id in organization_ids:
        if org_id == 138480:
            continue
        machines_link = f'https://sandboxapi.deere.com/platform/organizations/{org_id}/machines' + ';count=100'
        all_machines_current_org = get_with_paginate_helper(oauth2_session, machines_link, MYJOHNDEERE_V3_JSON_HEADERS,
                                                            embed_request_param)
        all_machines.extend(all_machines_current_org)

    print('Machines found: ' + str(len(all_machines)))

    machine_ids = [machine['id'] for machine in all_machines]

    # Getting Engine Hours

    end_date = datetime.now()
    end_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=1)

    start_date_str = start_date.strftime(DATE_FORMAT)
    end_date_str = end_date.strftime(DATE_FORMAT)

    params = {
        'startDate': start_date_str,
        'endDate': end_date_str
    }

    daily_engine_hours = []
    for jd_machine_id in machine_ids:
        machine_enginehours_link = f'https://sandboxapi.deere.com/platform/machines/{jd_machine_id}/engineHours' + ';count=100'
        machine_enginehours = get_with_paginate_helper(oauth2_session, machine_enginehours_link,
                                                       MYJOHNDEERE_V3_JSON_HEADERS, params)
        for machine_enginehour in machine_enginehours:
            new_engineHour_dict = {}
            new_engineHour_dict['machine_engine_hours_machine_id'] = jd_machine_id
            new_engineHour_dict['machine_engine_hours_reading_value'] = machine_enginehour['reading']['valueAsDouble']
            new_engineHour_dict['machine_engine_hours_report_time'] = machine_enginehour['reportTime']
            new_engineHour_dict['machine_engine_hours_source'] = machine_enginehour.get('source', '')
            new_engineHour_dict['machine_engine_hours_reading_unit'] = machine_enginehour['reading']['unit']
            daily_engine_hours.append(new_engineHour_dict)
        time.sleep(0.1)

    csv_header = ['machine_engine_hours_machine_id', 'machine_engine_hours_report_time',
                  'machine_engine_hours_source', 'machine_engine_hours_reading_value',
                  'machine_engine_hours_reading_unit']
    bucket_name = 'insightsdsc-use2-sandbox-shared-glue-resources'
    csv_file_name = 'engine_hours.csv'

    with open('/tmp/' + csv_file_name, 'w', newline='') as csvfile:
        csvwriter = csv.DictWriter(csvfile, fieldnames=csv_header)
        csvwriter.writeheader()
        for item in daily_engine_hours:
            csvwriter.writerow(item)

    session = boto3.session.Session()
    s3c = session.client(
        service_name="s3",
    )

    s3c.upload_file('/tmp/' + csv_file_name, bucket_name, "data/john-deere/engine-hours/date={date}/".format(
        date=start_date.strftime("%Y%m%d")) + csv_file_name)

    return {
        'message': "Uploaded {engine_hours} engine hours for {machines} machines to S3 for date {date}".format(
            engine_hours=len(daily_engine_hours), machines=len(machine_ids), date=start_date.strftime("%Y-%m-%d"))
    }
