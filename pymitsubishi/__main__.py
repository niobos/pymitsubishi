import argparse

from pymitsubishi import MitsubishiController

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("host", help="Hostname or IP address to connect to, optionally followed by ':port'")
args = parser.parse_args()

ctrl = MitsubishiController.create(args.host)
ctrl.fetch_status()
print(ctrl.get_status_summary())
