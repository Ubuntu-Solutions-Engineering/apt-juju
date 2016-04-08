from conjure.ui.views.services import ServicesView
from ubuntui.ev import EventLoop
from conjure.juju import Juju
from functools import partial
from conjure import async
from conjure.models.bundle import BundleModel
from conjure.utils import pollinate
import os.path as path
import json
from subprocess import check_output


class FinishController:

    def __init__(self, app):
        self.app = app
        self._post_exec_pollinate = False
        self._pre_exec_pollinate = False

    def handle_exception(self, tag, exc):
        pollinate(self.app.session_id, tag, self.app.log)
        self.app.ui.show_exception_message(exc)

    def handle_post_execption(self, exc):
        """ If an exception occurs in the post processing,
        log it but don't die
        """
        self.app.log.exception(exc)

    def _pre_exec(self, *args):
        """ Executes a bundles pre processing script if exists
        """
        self.app.log.debug("pre_exec start: {}".format(args))
        self._pre_exec_sh = path.join('/usr/share/',
                                      self.app.config['name'],
                                      'bundles',
                                      BundleModel.key(),
                                      'pre.sh')
        if not path.isfile(self._pre_exec_sh):
            self.app.log.debug(
                "Unable to find: {}, skipping".format(self._pre_exec_sh))
            self._deploy_bundle()
        self.app.ui.set_footer('Running pre-processing tasks.')
        if not self._pre_exec_pollinate:
            pollinate(self.app.session_id, 'XA', self.app.log)
            self._pre_exec_pollinate = True
        cmd = ("bash {script}".format(script=self._pre_exec_sh))
        self.app.log.debug("pre_exec running {}".format(cmd))

        try:
            future = async.submit(partial(check_output,
                                          cmd,
                                          shell=True,
                                          env=self.app.env),
                                  partial(self.handle_exception,
                                          "E002"))
            future.add_done_callback(self._pre_exec_done)
        except Exception as e:
            self.handle_exception("E002", e)

    def _pre_exec_done(self, future):
        result = json.loads(future.result().decode('utf8'))
        self.app.log.debug("pre_exec_done: {}".format(result))
        if result['returnCode'] > 0:
            raise Exception(
                'There was an error during the pre processing phase.')
        self._deploy_bundle()

    def _deploy_bundle(self):
        """ Performs the bootstrap in between processing scripts
        """
        self.app.log.debug("Deploying bundle")
        self.app.ui.set_footer('Deploying bundle')
        pollinate(self.app.session_id, 'DS', self.app.log)
        future = async.submit(
            partial(Juju.deploy_bundle, self.bundle),
            partial(self.handle_exception, "ED"))
        future.add_done_callback(self._deploy_bundle_done)

    def _deploy_bundle_done(self, future):
        result = future.result()
        self.app.log.debug("deploy_bundle_done: {}".format(result))
        if result.code > 0:
            self.handle_exception("ED", Exception(
                'There was an error during the post processing phase.'))
            return
        pollinate(self.app.session_id, 'DC', self.app.log)
        EventLoop.set_alarm_in(1, self._post_exec)

    def _post_exec(self, *args):
        """ Executes a bundles post processing script if exists
        """
        self._post_exec_sh = path.join('/usr/share/',
                                       self.app.config['name'],
                                       'bundles',
                                       BundleModel.key(),
                                       'post.sh')

        if not path.isfile(self._post_exec_sh):
            self.app.log.debug(
                "Unable to find: {}, skipping".format(self._post_exec_sh))
            return

        if not self._post_exec_pollinate:
            # We dont want to keep pollinating since this routine could
            # run multiple times
            pollinate(self.app.session_id, 'XB', self.app.log)
            self._post_exec_pollinate = True

        cmd = ("bash {script}".format(script=self._post_exec_sh))

        self.app.log.debug("post_exec running: {}".format(cmd))
        future = async.submit(partial(check_output,
                                      cmd,
                                      shell=True,
                                      env=self.app.env),
                              self.handle_post_execption)
        future.add_done_callback(self._post_exec_done)

    def _post_exec_done(self, future):
        try:
            result = json.loads(future.result().decode('utf8'))
            self.app.log.debug("post_exec_done: {}".format(result))
            self.app.ui.set_footer(result['message'])
            if result['returnCode'] > 0 or not result['isComplete']:
                self.app.log.error(
                    'There was an error during the post processing '
                    'phase, retrying.')
                EventLoop.set_alarm_in(1, self._post_exec)
            else:
                EventLoop.remove_alarms()
                self.app.ui.set_footer('Post processing completed.')
        except Exception as e:
            self.app.log.error(e)
            self.handle_exception("E002", e)

    def refresh(self, *args):
        self.view.refresh_nodes()
        EventLoop.set_alarm_in(1, self.refresh)

    def render(self, bundle):
        """ Render services status view

        Arguments:
        bundle: modified bundle to deploy
        """
        self.bundle = bundle
        self.view = ServicesView(self.app)

        self.app.ui.set_header(
            title="Status: {}".format(
                self.app.config['summary'])
        )
        self.app.ui.set_body(self.view)
        self.app.ui.set_subheader('Deploy Status - (Q)uit')

        if not self.app.argv.status_only:
            EventLoop.set_alarm_in(1, self._pre_exec)
        EventLoop.set_alarm_in(1, self.refresh)
