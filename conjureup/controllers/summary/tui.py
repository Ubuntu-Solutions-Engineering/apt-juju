import os
import sys

from prettytable import PrettyTable
from termcolor import colored

from conjureup import events, utils
from conjureup.app_config import app
from conjureup.controllers.summary import common


class SummaryController:

    def __init__(self):
        self.save_path = os.path.join(app.config['spell-dir'],
                                      'results.txt')

    def render(self, results):
        common.write_results(results, self.save_path)
        utils.info("Summary")
        table = PrettyTable()
        table.field_names = ["Application", "Result"]
        for k, v in results.items():
            if sys.__stdin__.isatty():
                application_name = colored(k, 'blue', attrs=['bold'])
                result = colored(v, 'green', attrs=['bold'])
            else:
                application_name = k
                result = v
            table.add_row([application_name, result])
        print(table)
        utils.info("Installation of your big software is now complete.")
        events.Shutdown.set(0)


_controller_class = SummaryController
