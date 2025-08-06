import argparse
import logging
from pprint import pprint

from pymitsubishi import MitsubishiController, PowerOnOff, DriveMode

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--verbose', '-v', help="Verbose output", action="count", default=0)
parser.add_argument("host", help="Hostname or IP address to connect to, optionally followed by ':port'")
parser.add_argument("--power", help="Change power mode", choices=['on', 'off'])
parser.add_argument("--mode", help="Change mode", choices=[_.name for _ in DriveMode])
parser.add_argument("--target-temperature", help="Change the target temperature", type=float)
args = parser.parse_args()

logging.basicConfig(level=logging.WARNING - 10 * args.verbose)
logger = logging.getLogger(__name__)

ctrl = MitsubishiController.create(args.host)
ctrl.fetch_status()
pprint(ctrl.get_status_summary())

changes = False
if args.mode:
    changes = True
    ctrl.set_mode(DriveMode[args.mode])
if args.power:
    changes = True
    ctrl.set_power(args.power == 'on')
if args.target_temperature:
    changes = True
    ctrl.set_temperature(args.target_temperature)

if changes:
    print()
    print("After changes:")
    pprint(ctrl.get_status_summary())
