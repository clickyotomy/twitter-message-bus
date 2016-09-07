#! /usr/bin/env python2.7

'''
Manage the disque (redis queue) instance; listen to tweets using Twitter's
Streaming API, dump them into the 'in' queue.
'''

import re
import json
from argparse import ArgumentParser
from logging import (NullHandler, getLogger, StreamHandler, Formatter, DEBUG,
                     INFO)

import tweepy
from pydisque.client import Client

# Formatting for logger output.
getLogger(__name__).addHandler(NullHandler())
LOGGER = getLogger()
HANDLER = StreamHandler()
FORMATTER = Formatter(
    ('%(asctime)s; log: %(name)s, %(levelname)s, %(levelno)s; '
     'process: %(process)s - %(processName)s; path: %(pathname)s '
     'L%(lineno)s - module: %(module)s, method: %(funcName)s; '
     'error: %(exc_info)s; message: %(message)s')
)
HANDLER.setFormatter(FORMATTER)


'''
Credentials are stored here, change this path and the load_credentials()
method to override defaults.

Notes:
    [*] Get a personal access token on Github: https://git.io/vmNUX;
        make sure you include 'gist' in the scope.
    [*] Get a personal access token for your application on Twitter:
        https://dev.twitter.com/oauth/overview/application-owner-access-tokens;
        make sure you create an application before you create the access
        tokens.
    [*] API error codes: https://dev.twitter.com/overview/api/response-codes

By defualt, keys are stored this way (in JSON):
    {
        "github": "github-personal-access-token",
        "twitter": {
            "consumer-key": "twitter-app-consumer-key",
            "consumer-secret": "twitter-app-consuer-secret",
            "access-token": "twitter-app-access-token"
            "access-token-secret": "twitter-app-access-token-secret"
        }
    }
'''
VAULT_PATH = 'vault/keys.json'


def load_credentials(path=VAULT_PATH):
    '''
    Load credentials from vault.
    '''
    api = None
    with open(path, 'r') as vault_file:
        try:
            vault = json.loads(vault_file.read())
            auth = tweepy.OAuthHandler(vault['twitter']['consumer-key'],
                                       vault['twitter']['consumer-secret'])
            auth.set_access_token(vault['twitter']['access-token'],
                                  vault['twitter']['access-token-secret'])
            api = tweepy.API(auth)

        except IOError:
            print 'Unable to read vault-file: {0}.'.format(path)
        except (KeyError, ValueError):
            print 'Unable to parse the vault-file.'

    return api


class StreamDaemon(tweepy.StreamListener):
    '''
    Listen to Twitter.
    '''
    def __init__(self, queue):
        '''
        Adds queue to the derived class.
        '''
        super(StreamDaemon, self).__init__()
        self.queue = queue

    def on_status(self, status):
        '''
        Do this, when you receive a new status.
        '''
        __id = status.id
        __from = status.author.screen_name
        __content = status.text.strip()
        __timestamp = status.timestamp_ms

        log = ('[tweet] id: {0}; timestamp: {1}; '
               'from: {2}; content: {3}').format(__id, __timestamp, __from,
                                                 __content)
        LOGGER.info(log)

        # Push the message to the 'in' queue.
        try:
            __job_id = self.queue.add_job('in', __content)
            LOGGER.info('[queued] job-id: %s', __job_id)
        except Exception:
            LOGGER.critical('[queue-error]: Unable to add job; message lost.')

    def on_error(self, status):
        '''
        Do something when you get a non 200 HTTP response.
        '''
        link = 'https://dev.twitter.com/overview/api/response-codes'
        LOGGER.error('[error] received a %s; check %s', status, link)
        return

    def on_timeout(self):
        '''
        Send out a message on timeout.
        '''
        LOGGER.error('[error] received timeout!')
        return

    def on_warning(self, notice):
        '''
        Print out the warning notice.
        '''
        LOGGER.warning('[warning] notice: %s', notice)
        return

    def on_limit(self, track):
        '''
        Notify on rate-limiting.
        '''
        LOGGER.warning('[warning] approaching rate-limit; %s', track)
        return


def main():
    '''
    This is the main method.
    '''
    message = 'Listen to tweets; dump them to the queue.'
    socket_help = ('a list containing the hosts, port numbers to listen to; '
                   'defaults to localhost:7711 (for disque)')

    parser = ArgumentParser(description=message)
    parser.add_argument('-s', '--sockets', help=socket_help,
                        default=['localhost:7711'], dest='sockets',
                        metavar=('HOST:PORT'), nargs='+')
    parser.add_argument('-c', '--channels', help='Twitter accounts to follow',
                        dest='channels', metavar=('CHANNEL'), nargs='+',
                        required=True)
    parser.add_argument('-d', '--debug', help='enable debugging',
                        action='store_true', default=False)

    args = vars(parser.parse_args())

    if args['debug']:
        LOGGER.setLevel(DEBUG)
        LOGGER.addHandler(HANDLER)
    else:
        LOGGER.setLevel(INFO)
        LOGGER.addHandler(HANDLER)

    try:
        # Connect to the redis-queue.
        queue = Client(args['sockets'])
        queue.connect()
        LOGGER.info('[start-daemon]')
        queue_info = json.dumps(queue.info(), indent=4)
        LOGGER.info('[queue-init]\n%s', queue_info)

        # Load credentials, initialize authentication module, listen to tweets.
        api = load_credentials()
        listener = StreamDaemon(queue)
        streamer = tweepy.Stream(auth=api.auth, listener=listener)
        args['channels'] = [re.sub('@', '', _) for _ in args['channels']]
        streamer.userstream(track=args['channels'])

    except Exception:
        LOGGER.error('[error] unable to connect to the redis-queue (disque)!')

    except KeyboardInterrupt:
        LOGGER.critical('[stop-daemon]')
    return


if __name__ == '__main__':
    main()
