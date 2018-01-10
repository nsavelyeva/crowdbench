import socket
import argparse
from app import app


parser = argparse.ArgumentParser(description='Start CrowdBench app.')

parser.add_argument('-s', '--server', default='0.0.0.0',
                    help='IP address of a network interface for CrowdBench to run on.',
                    required=False)
parser.add_argument('-p', '--port', default=80, type=int,
                    help='a port number for CrowdBench to listen on.',
                    required=False)
parser.add_argument('-v', '--verbose', default=False, type=bool,
                    help='verbose mode, debug messages will be displayed.',
                    required=False)

args = vars(parser.parse_args())


try:
    app.run(host=args['server'], port=args['port'], debug=args['verbose'], use_reloader=False)
except socket.gaierror as err:
    print('Cannot start CrowdBench app due to socket error:\n\t%s.' % err)
    print('Is the network interface %s correct?' % args['server'])
    print('Try "run.py -h" to see launching options.')
except OSError as err:
    print('Cannot start CrowdBench app due to OS error:\n\t%s.' % err)
    print('Is the port %s already in use?' % args['port'])
    print('Try "run.py -h" to see launching options.')
