import base64
import boto3
import ast


def get_secret(secret_name: str) -> dict:
    """Returns a secret dictionary from secrets manager."""
    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name="secretsmanager",
    )

    # get secret, no error handling
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    if "SecretString" in get_secret_value_response:
        secret = get_secret_value_response["SecretString"]
        secret = ast.literal_eval(secret)
    else:
        # decoded binary secret
        secret = base64.b64decode(get_secret_value_response["SecretBinary"])
    return secret


def get_with_paginate_helper(oauth2_session, initial_link, headers, params={}, ignore_skips=False):
    response = oauth2_session.get(initial_link, headers=headers, params=params)

    if response.status_code > 399:
        if not ignore_skips:
            print('Skipped')
        return []
    currentPage_link = None
    nextPage_link = None

    for link_object in response.json()['links']:
        if (link_object['rel'] == 'self'):
            currentPage_link = link_object['uri']
        if (link_object['rel'] == 'nextPage'):
            nextPage_link = link_object['uri']
            break;

    responses_list = response.json()['values']

    while currentPage_link != nextPage_link and nextPage_link:
        response2 = oauth2_session.get(nextPage_link, headers=headers)
        for link_object in response2.json()['links']:
            if (link_object['rel'] == 'self'):
                currentPage_link = link_object['uri']
            if (link_object['rel'] == 'nextPage'):
                nextPage_link = link_object['uri']
                break;
        responses_list.extend(response2.json()['values'])
    return responses_list