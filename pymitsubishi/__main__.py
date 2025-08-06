import argparse
import logging

from pymitsubishi import MitsubishiController


parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--verbose', '-v', help="Verbose output", action="count", default=0)
parser.add_argument("host", help="Hostname or IP address to connect to, optionally followed by ':port'")
args = parser.parse_args()

logging.basicConfig(level=logging.WARNING - 10 * args.verbose)
logger = logging.getLogger(__name__)

ctrl = MitsubishiController.create(args.host)
ctrl.fetch_status()
print(ctrl.get_status_summary())
