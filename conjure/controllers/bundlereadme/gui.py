from ubuntui.ev import EventLoop

from conjure import controllers
from conjure.app_config import app
from conjure.ui.views.bundle_readme_view import BundleReadmeView
from conjure import utils


class BundleReadmeController:

    def __init__(self):
        self.bundle_filename = None
        self.bundle = None
        self.services = []

    def __handle_exception(self, tag, exc):
        utils.pollinate(app.session_id, tag)
        app.ui.show_exception_message(exc)
        EventLoop.remove_alarms()

    def finish(self):
        return controllers.use('deploy').render()

    def render(self):
        _, rows = EventLoop.screen_size()
        rows = int(rows * .75)
        brmv = BundleReadmeView(app.metadata_controller,
                                self.finish, rows)
        app.ui.set_header("Review Spell")
        app.ui.set_body(brmv)


_controller_class = BundleReadmeController
