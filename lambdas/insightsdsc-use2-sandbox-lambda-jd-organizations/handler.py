import base64
import requests
from requests_oauthlib import OAuth2Session
import boto3
import ast
import json
import csv
from lambdas.utils.utils import get_secret, get_with_paginate_helper

MYJOHNDEERE_V3_JSON_HEADERS = {'Accept': 'application/vnd.deere.axiom.v3+json',
                               'Content-Type': 'application/vnd.deere.axiom.v3+json'}


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

    print('Well Known Token Grant URL - ' + TOKEN_GRANT_URL)

    SCOPES_TO_REQUEST = {'offline_access', 'ag1', 'eq1', 'files'}
    oauth2_session = OAuth2Session(CLIENT_ID, redirect_uri=CLIENT_REDIRECT_URI, scope=SCOPES_TO_REQUEST)

    REFRESH_TOKEN = deere_app_creds['refresh_token']
    token_response = oauth2_session.refresh_token(TOKEN_GRANT_URL, refresh_token=REFRESH_TOKEN,
                                                  auth=(CLIENT_ID, CLIENT_SECRET))

    API_CATALOG_URI = 'https://sandboxapi.deere.com/platform/'

    api_catalog_response = oauth2_session.get(API_CATALOG_URI, headers=MYJOHNDEERE_V3_JSON_HEADERS)
    links_array_from_api_catalog_response = api_catalog_response.json()['links']

    organizations_link = None

    for link_object in links_array_from_api_catalog_response:
        if (link_object['rel'] == 'organizations'):
            organizations_link = link_object['uri']
            break;

    organizations_link1 = organizations_link + ';count=100'

    all_orgs = get_with_paginate_helper(oauth2_session, organizations_link1, MYJOHNDEERE_V3_JSON_HEADERS)

    session = boto3.session.Session()
    s3 = session.client(
        service_name="s3",
    )

    csv_header = set()
    for item in all_orgs:
        csv_header.update(item.keys())

    csv_header = list(csv_header)

    bucket_name = 'insightsdsc-use2-sandbox-shared-glue-resources'
    csv_file_name = 'organizations.csv'

    with open('/tmp/' + csv_file_name, 'w', newline='') as csvfile:
        csvwriter = csv.DictWriter(csvfile, fieldnames=csv_header)
        csvwriter.writeheader()
        for item in all_orgs:
            csvwriter.writerow(item)

    s3.upload_file('/tmp/' + csv_file_name, bucket_name, "data/john-deere/" + csv_file_name)

    return {
        'message': "{orgs} organizations uploaded to S3".format(orgs=len(all_orgs))
    }
