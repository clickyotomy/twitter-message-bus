#! /usr/bin/env python2.7

'''
Post, fetch or delete a gist (containing the keybase-saltpack) on GitHub.
'''

import os
import json
import hashlib
from socket import getfqdn
from getpass import getuser
from datetime import datetime

import requests

# API URL, headers.
GITHUB_API_URL = 'https://api.github.com'
GITHUB_HEADERS = {
    'Accept': 'application/vnd.github.v3.raw+json'
}


def http_debug(response):
    '''
    Print the HTTP request/response debug log.
    '''
    print 'http-request\n{0}\n'.format('-' * len('http-request'))
    print 'url ({0}): {1}'.format(response.request.method,
                                  response.request.url)
    print 'request-headers:'
    print json.dumps(dict(response.request.headers), indent=4)
    if response.request.method != 'GET':
        if response.request.body is not None:
            print 'request-payload:'
            print json.dumps(json.loads(response.request.body), indent=4)
    print '\nhttp-response\n{0}\n'.format('-' * len('http-response'))
    print 'status-code: {0} {1}'.format(response.status_code, response.reason)
    print 'url: {0}'.format(response.url)
    print 'time-elapsed: {0}s'.format(response.elapsed.total_seconds())
    print 'response-headers:'
    print json.dumps(dict(response.headers), indent=4)
    print 'response-content:'
    print None if response.content is '' else json.dumps(response.json(),
                                                         indent=4)


def github(http, uri, token, payload, debug=False):
    '''
    Make an HTTP request to the GitHub API.
    '''
    if uri is not None:
        url = '/'.join([GITHUB_API_URL, uri.lstrip('/')])

    if token is not None:
        GITHUB_HEADERS.update({'Authorization': ' '.join(['token', token])})

    request = getattr(requests, http)

    try:
        response = request(url, data=payload, headers=GITHUB_HEADERS)
        if debug:
            http_debug(response)
        return response.json()
    except (requests.exceptions.RequestException, ValueError):
        return {}


def post(content, token=None, username=None, public=False, debug=False):
    '''
    Post a gist on GitHub.
    '''
    random = hashlib.sha1(os.urandom(16)).hexdigest()
    username = getuser() if username is None else username
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    description = ('{hash} (twitter-message-bus); from {host} by {user} '
                   'at {time} UTC.').format(host=getfqdn(), user=username,
                                            time=now, hash=random)

    payload = json.dumps({
        'files': {
            'message': {
                'content': content
            }
        },
        'public': public,
        'description': description
    })

    response = github(http='post', uri='gists', token=token, payload=payload,
                      debug=debug)
    return response['id'] if 'id' in response.keys() else None


def get(gist_id, token=None, debug=False):
    '''
    Get the contents of the gist from GitHub.
    '''
    response = github(http='get', uri='gists/{0}'.format(gist_id), token=token,
                      payload=None, debug=debug)

    if 'files' in response.keys():
        return response['files']['message']['content']
    return None


def delete(gist_id, token=None, debug=False):
    '''
    Delete a gist from GitHub.
    '''
    response = github(http='delete', uri='gists/{0}'.format(gist_id),
                      token=token, payload=None, debug=debug)
    return True if response == {} else False
