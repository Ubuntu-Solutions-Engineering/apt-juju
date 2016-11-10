import json
import os
from functools import partial
from operator import attrgetter
from subprocess import PIPE

from conjureup import async, controllers, juju, utils
from conjureup.api.models import model_info
from conjureup.app_config import app
from conjureup.telemetry import track_event, track_exception, track_screen
from conjureup.ui.views.applicationconfigure import ApplicationConfigureView
from conjureup.ui.views.applicationlist import ApplicationListView
from ubuntui.ev import EventLoop


class DeployController:

    def __init__(self):
        self.applications = []

    def _handle_exception(self, tag, exc):
        track_exception(exc.args[0])
        app.ui.show_exception_message(exc)
        self.showing_error = True
        EventLoop.remove_alarms()

    def _pre_deploy_exec(self):
        """ runs pre deploy script if exists
        """
        app.env['JUJU_PROVIDERTYPE'] = model_info(
            app.current_model)['provider-type']
        app.env['JUJU_CONTROLLER'] = app.current_controller
        app.env['JUJU_MODEL'] = app.current_model

        pre_deploy_sh = os.path.join(app.config['spell-dir'],
                                     'steps/00_pre-deploy')
        if os.path.isfile(pre_deploy_sh) \
           and os.access(pre_deploy_sh, os.X_OK):
            track_event("Juju Pre-Deploy", "Started", "")
            msg = "Running pre-deployment tasks."
            app.log.debug(msg)
            app.ui.set_footer(msg)
            return utils.run(pre_deploy_sh,
                             shell=True,
                             stdout=PIPE,
                             stderr=PIPE,
                             env=app.env)
        return json.dumps({'message': 'No pre deploy necessary',
                           'returnCode': 0,
                           'isComplete': True})

    def _pre_deploy_done(self, future):
        try:
            result = json.loads(future.result().stdout.decode())
        except AttributeError:
            result = json.loads(future.result())
        except:
            return self._handle_exception(
                'E003',
                Exception(
                    "Problem with pre-deploy: \n{}, ".format(
                        future.result())))

        app.log.debug("pre_deploy_done: {}".format(result))
        if result['returnCode'] > 0:
            track_exception("Pre-deploy error")
            return self._handle_exception('E003', Exception(
                'There was an error during the pre '
                'deploy processing phase: {}.'.format(result)))
        else:
            app.ui.set_footer("Pre-deploy processing done.")

    def do_configure(self, application, sender):
        "shows configure view for application"
        cv = ApplicationConfigureView(application,
                                      app.metadata_controller,
                                      self)
        app.ui.set_header("Configure {}".format(application.service_name))
        app.ui.set_body(cv)

    def handle_configure_done(self):
        app.ui.set_header(self.list_header)
        self.list_view.update()
        app.ui.set_body(self.list_view)

    def do_deploy(self, application, msg_cb):
        "launches deploy in background for application"
        self.undeployed_applications.remove(application)

        def msg_both(*args):
            msg_cb(*args)
            app.ui.set_footer(*args)

        juju.deploy_service(application,
                            app.metadata_controller.series,
                            msg_cb=msg_both,
                            exc_cb=partial(self._handle_exception, "ED"))

    def do_deploy_remaining(self):
        "deploys all un-deployed applications"
        for application in self.undeployed_applications:
            juju.deploy_service(application,
                                app.metadata_controller.series,
                                app.ui.set_footer,
                                partial(self._handle_exception, "ED"))

    def finish(self):
        juju.set_relations(self.applications,
                           app.ui.set_footer,
                           partial(self._handle_exception, "ED"))

        if app.bootstrap.running and not app.bootstrap.running.done():
            return controllers.use('bootstrapwait').render()
        else:
            return controllers.use('deploystatus').render()

    def render(self):
        track_screen("Deploy")
        try:
            future = async.submit(self._pre_deploy_exec,
                                  partial(self._handle_exception, 'E003'),
                                  queue_name=juju.JUJU_ASYNC_QUEUE)
            future.add_done_callback(self._pre_deploy_done)
        except Exception as e:
            return self._handle_exception('E003', e)

        juju.add_machines(
            list(app.metadata_controller.bundle.machines.values()),
            exc_cb=partial(self._handle_exception, "ED"))

        self.applications = sorted(app.metadata_controller.bundle.services,
                                   key=attrgetter('service_name'))
        self.undeployed_applications = self.applications[:]

        self.list_view = ApplicationListView(self.applications,
                                             app.metadata_controller,
                                             self)
        self.list_header = "Review and Configure Applications"
        app.ui.set_header(self.list_header)
        app.ui.set_body(self.list_view)

_controller_class = DeployController
