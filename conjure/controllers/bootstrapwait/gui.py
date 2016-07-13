from conjure.ui.views.bootstrapwait import BootstrapWaitView
from conjure.app_config import app
from conjure import controllers
from ubuntui.ev import EventLoop
import sys

this = sys.modules[__name__]
this.alarm_handle = None


def finish(*args):
    if this.alarm_handle:
        EventLoop.remove_alarm(this.alarm_handle)
    return controllers.use('deploystatus').render()


def __refresh(*args):
    this.view.redraw_kitt()
    this.alarm_handle = EventLoop.set_alarm_in(1, __refresh)


def render():
    app.log.debug("Rendering bootstrap wait")

    this.view = BootstrapWaitView(
        app=app,
        message="Juju Controller is initializing. Please wait.")
    app.ui.set_header(title="Waiting")
    app.ui.set_body(this.view)

    app.bootstrap.running.add_done_callback(finish)
    __refresh()
