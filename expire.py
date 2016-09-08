#! /usr/bin/env python2.7

'''
Handle deletion of tweets/gists based on their expiry.
Listens to disque on the 'out' queue.
Spawn any number of instances of this module to achieve parallel deletions.
Servicing jobs is done in a round-robin manner.
'''

import time
import json
from datetime import datetime
from argparse import ArgumentParser
from logging import (NullHandler, getLogger, StreamHandler, Formatter, DEBUG,
                     INFO)

import tweepy
from pydisque.client import Client

from gist import delete

# Formatting for logger output.
getLogger(__name__).addHandler(NullHandler())
LOGGER = getLogger()
HANDLER = StreamHandler()
FORMATTER = Formatter(
    ('%(asctime)s; %(name)s, %(levelname)s; PID: %(process)s; '
     '%(module)s: %(funcName)s; traceback: %(exc_info)s; %(message)s')
)
HANDLER.setFormatter(FORMATTER)

# Check stream.py for more information.
VAULT_PATH = 'vault/keys.json'


def remove(what, which, auth, debug=False):
    '''
    Delete a gist/tweet, based on the given ID.
    '''
    flag = None
    LOGGER.info('[req-delete-%s] %s', what, which)

    if what == 'gist':
        flag = delete(which, auth, debug)
    elif what == 'tweet':
        _flag = auth.destroy_status(which)
        LOGGER.debug('[debug-delete-tweet] %s', _flag)
        flag = True or _flag
    else:
        LOGGER.error('[delete] unknown-entity')

    LOGGER.info('[status-delete-%s-%s] %s', what, which, flag)


def listen(queue, tokens, debug=False, retry=8):
    '''
    Listen to the queue, ACK if the job timestamp >= current-timestamp,
    else NACK.
    Currently, the retry is set to N = 3, so hit ^C thrice to get out.
    '''
    try:
        while True:
            job = queue.get_job(['out'], count=1, nohang=False)
            auth = None
            # Wait for a message.
            if len(job) > 0:
                LOGGER.info('[processing] %s', repr(job[0]))
                try:
                    what, which, timestamp = job[0][2].split('~')
                except IndexError:
                    queue.ack_job(job[0][1])
                    LOGGER.error('[queue] invalid message!')
                    continue
                future, now = (int(timestamp),
                               int(datetime.utcnow().strftime('%s')))
                # Compare timestamps.
                if future <= now:
                    if what == 'gist':
                        auth = tokens[0]
                    elif what == 'tweet':
                        auth = tokens[1]
                    # Delete the tweet/gist.
                    remove(what, which, auth, debug)
                    queue.ack_job(job[0][1])

                else:
                    LOGGER.info('[push-back] ttl-diff-seconds: %d',
                                (future - now))
                    # If the timestamp hasn't expired, push the job back to
                    # queue.
                    queue.ack_job(job[0][1])
                    queue.del_job(job[0][1])
                    queue.add_job('out', job[0][2])
            time.sleep(retry)

    except Exception as _error:
        LOGGER.error('[delete-error] %s', _error)

    except KeyboardInterrupt:
        return


def load_credentials(path=VAULT_PATH):
    '''
    Load credentials from vault.
    '''
    gist, api = None, None
    with open(path, 'r') as vault_file:
        try:
            vault = json.loads(vault_file.read())
            auth = tweepy.OAuthHandler(vault['twitter']['consumer-key'],
                                       vault['twitter']['consumer-secret'])
            auth.set_access_token(vault['twitter']['access-token'],
                                  vault['twitter']['access-token-secret'])
            api = tweepy.API(auth)
            gist = vault['github']

        except IOError:
            print 'Unable to read vault-file: {0}.'.format(path)
        except (KeyError, ValueError):
            print 'Unable to parse the vault-file.'

    return gist, api


def main():
    '''
    Initialize authentication, client connection.
    '''
    message = 'Delete gists, tweets if a TTL is set.'
    socket_help = ('a list containing the host, port numbers to listen to; '
                   'defaults to localhost:7711 (for disque)')
    retry_help = 'queue check frequncy (in seconds); defaults to 8'

    parser = ArgumentParser(description=message)
    parser.add_argument('-s', '--sockets', help=socket_help,
                        default=['localhost:7711'], dest='sockets',
                        metavar=('HOST:PORT'), nargs='+')
    parser.add_argument('-d', '--debug', help='enable debugging',
                        action='store_true', default=False)
    parser.add_argument('-r', '--retry', help=retry_help, default=8,
                        type=int, metavar=('DELAY'))

    args = vars(parser.parse_args())

    if args['debug']:
        LOGGER.setLevel(DEBUG)
        LOGGER.addHandler(HANDLER)
    else:
        LOGGER.setLevel(INFO)
        LOGGER.addHandler(HANDLER)

    # Load the credentials.
    tokens = load_credentials()

    if None in tokens:
        LOGGER.error('[load_credentials] unable to load credentials!')
        return

    try:
        # Connect to the redis-queue.
        queue = Client(args['sockets'])
        queue.connect()
        LOGGER.info('[start-daemon]')
        queue_info = json.dumps(queue.info(), indent=4)
        LOGGER.debug('[queue-init]\n%s', queue_info)
        listen(queue, tokens, args['debug'], args['retry'])

    except Exception:
        LOGGER.error('[error] unable to connect to the redis-queue (disque)!')

    except KeyboardInterrupt:
        LOGGER.critical('[stop-daemon]')

    return

if __name__ == '__main__':
    main()
