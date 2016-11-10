import os

from conjureup.app_config import app
from conjureup.controllers.summary import common
from conjureup.telemetry import track_screen
from conjureup.ui.views.summary import SummaryView
from ubuntui.ev import EventLoop


class SummaryController:

    def __init__(self):
        self.view = None
        self.save_path = os.path.join(app.config['spell-dir'],
                                      'results.txt')

    def finish(self):
        EventLoop.remove_alarms()
        EventLoop.exit(0)

    def render(self, results):
        track_screen("Summary")
        app.log.debug("Rendering summary results: {}".format(results))

        common.write_results(results, self.save_path)
        self.view = SummaryView(app, results, self.finish)
        app.ui.set_header(title="Deploy Summary",
                          excerpt="Deployment summary for {}".format(
                              app.config['spell']))
        app.ui.set_body(self.view)
        app.ui.set_footer("Your big software is deployed, press "
                          "(Q) key to return to shell.")

_controller_class = SummaryController
