import sys

from ubuntui.ev import EventLoop

from conjure import controllers
from conjure.app_config import app
from conjure.ui.views.bundle_readme_view import BundleReadmeView
from conjure import utils
from conjure.controllers.deploy.common import (get_bundleinfo,
                                               get_metadata_controller)

this = sys.modules[__name__]
this.bundle_filename = None
this.bundle = None
this.services = []


def __handle_exception(tag, exc):
    utils.pollinate(app.session_id, tag)
    app.ui.show_exception_message(exc)
    EventLoop.remove_alarms()


def finish():
    return controllers.use('deploy').render()


def render():

    if not this.bundle:
        this.bundle_filename, this.bundle, this.services = get_bundleinfo()

    if not app.metadata_controller:
        app.metadata_controller = get_metadata_controller(this.bundle,
                                                          this.bundle_filename)
    _, rows = EventLoop.screen_size()
    rows = int(rows * .75)
    brmv = BundleReadmeView(app.metadata_controller, finish, rows)
    app.ui.set_header("Review Spell")
    app.ui.set_body(brmv)
