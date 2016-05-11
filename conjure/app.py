""" Application entrypoint
"""

from ubuntui.ev import EventLoop
from ubuntui.palette import STYLES
from conjure.ui import ConjureUI
from conjure.juju import Juju
from conjure import async
from conjure import __version__ as VERSION
from conjure.download import download, get_remote_url
from conjure.models.bundle import BundleModel
from conjure.controllers.welcome import WelcomeController
from conjure.controllers.finish import FinishController
from conjure.controllers.deploysummary import DeploySummaryController
from conjure.controllers.deploy import DeployController
from conjure.controllers.cloud import CloudController
from conjure.controllers.newcloud import NewCloudController
from conjure.controllers.jujucontroller import JujuControllerController
from conjure.controllers.bootstrapwait import BootstrapWaitController
from conjure.controllers.lxdsetup import LXDSetupController
from conjure.log import setup_logging
import json
import toml
import sys
import argparse
import os
import os.path as path
import uuid


class ApplicationException(Exception):
    """ Error in application
    """


class ApplicationConfig:
    """ Application config encapsulating common attributes
    used throughout the lifetime of the application.
    """
    def __init__(self, argv):
        # Try to load cache file
        self.cache = self.load()
        # Reference to entire UI
        self.ui = None
        # Global config attr
        self.config = self.cache.get('config', None)
        # CLI arguments
        self.argv = argv
        # List of all known controllers to be rendered
        self.controllers = None
        # Current Juju model
        self.current_model = self.cache.get('current_model', None)
        # Current controller
        self.current_controller = self.cache.get('current_controller',
                                                 None)
        # Global session id
        self.session_id = None
        # logger
        self.log = None
        # Environment to pass to processing tasks
        self.env = self.cache.get('env', os.environ.copy())

        # Is application deployment complete
        self.complete = self.cache.get('complete', False)

    def save(self):
        """ Create a cache of the current deployment containing the following

        Bundle key, deploy status, juju controller
        """
        cache_home_dir = os.environ.get('XDG_CACHE_HOME', os.path.join(
            os.path.expanduser('~'),
            '.cache'))
        try:
            cache_deploy_dir = os.path.join(cache_home_dir,
                                            Juju.current_controller(),
                                            Juju.current_model())
        except Exception as e:
            return self.ui.show_exception_message(e)

        if not os.path.isdir(cache_deploy_dir):
            os.makedirs(cache_deploy_dir)

        try:
            cache_file = os.path.join(cache_deploy_dir, 'cache.json')
            with open(cache_file, 'w') as cache_fp:
                json.dump({'config': self.config,
                           'current_model': self.current_model,
                           'current_controller': self.current_controller,
                           'env': self.env,
                           'complete': self.complete,
                           'selected_bundle': BundleModel.bundle}, cache_fp)
        except Exception as e:
            return self.ui.show_exception_message(e)

    def load(self):
        """ loads cache if applicable
        """
        cache_home_dir = os.environ.get('XDG_CACHE_HOME', os.path.join(
            os.path.expanduser('~'),
            '.cache'))
        try:
            cache_deploy_dir = os.path.join(cache_home_dir,
                                            Juju.current_controller(),
                                            Juju.current_model())
        except:
            return {}

        cache_file = os.path.join(cache_deploy_dir, 'cache.json')
        if path.isfile(cache_file):
            with open(cache_file) as cache_fp:
                return json.load(cache_fp)
        return {}


class Application:
    def __init__(self, argv, spell, metadata):
        """ init

        Arguments:
        argv: Options passed in from cli
        metadata: path to solutions metadata.json
        """
        self.app = ApplicationConfig(argv)
        self.app.session_id = os.getenv('CONJURE_TEST_SESSION_ID',
                                        '{}/{}'.format(
                                            spell,
                                            str(uuid.uuid4())))
        self.app.config = {'metadata': metadata, 'spell': spell}
        self.app.ui = ConjureUI()

        self.app.controllers = {
            'welcome': WelcomeController(self.app),
            'clouds': CloudController(self.app),
            'newcloud': NewCloudController(self.app),
            'lxdsetup': LXDSetupController(self.app),
            'bootstrapwait': BootstrapWaitController(self.app),
            'deploy': DeployController(self.app),
            'deploysummary': DeploySummaryController(self.app),
            'jujucontroller': JujuControllerController(self.app),
            'finish': FinishController(self.app)
        }

        self.app.log = setup_logging(spell,
                                     self.app.argv.debug)

    def unhandled_input(self, key):
        if key in ['q', 'Q']:
            async.shutdown()
            EventLoop.exit(0)

    def _start(self, *args, **kwargs):
        """ Initially load the welcome screen
        """
        if self.app.argv.status_only:
            self.app.controllers['finish'].render(bundle=None)
        else:
            self.app.controllers['welcome'].render()

    def start(self):
        EventLoop.build_loop(self.app.ui, STYLES,
                             unhandled_input=self.unhandled_input)
        EventLoop.set_alarm_in(0.05, self._start)
        EventLoop.run()


def parse_options(argv):
    parser = argparse.ArgumentParser(prog="conjure-up")
    parser.add_argument('spell', help="Specify the solution to "
                        "conjure, e.g. openstack")
    parser.add_argument('-d', '--debug', action='store_true',
                        dest='debug',
                        help='Enable debug logging.')
    parser.add_argument('-y', action='store_true',
                        help='Do not prompt during conjuring')
    parser.add_argument('-s', '--status', action='store_true',
                        dest='status_only',
                        help='Display the summary of the conjuring')
    parser.add_argument(
        '--version', action='version', version='%(prog)s {}'.format(VERSION))
    return parser.parse_args(argv)


def main():
    opts = parse_options(sys.argv[1:])
    if "/" in opts.spell:
        spell = opts.spell.split("/")[-1]
    else:
        spell = opts.spell

    if os.geteuid() == 0:
        print("")
        print("This should _not_ be run as root or with sudo.")
        print("")
        sys.exit(1)

    try:
        docs_url = "https://jujucharms.com/docs/stable/getting-started"
        juju_version = Juju.version()
        if int(juju_version[0]) < 2:
            print(
                "Only Juju v2 and above is supported, "
                "your currently installed version is {}.\n\n"
                "Please refer to {} for help on installing "
                "the correct Juju.".format(juju_version, docs_url))
            sys.exit(1)
    except Exception as e:
        print(e)
        sys.exit(1)

    with open('/etc/conjure.toml') as fp:
        global_conf = toml.loads(fp.read())

    if spell in global_conf['curated_spells']:
        metadata = path.join('/usr/share', spell, 'metadata.toml')

        if not path.exists(metadata):
            os.execl("/usr/share/conjure-up/do-apt-install",
                     "/usr/share/conjure-up/do-apt-install",
                     spell)
        with open(metadata) as fp:
            metadata = toml.loads(fp.read())

    else:
        # Check cache dir for spells
        spell_dir = os.environ.get('XDG_CACHE_HOME', os.path.join(
            os.path.expanduser('~'),
            '.cache/conjure-up', spell))

        if not path.isdir(spell_dir):
            os.makedirs(spell_dir)

        metadata = os.path.join(spell_dir, 'craft/metadata.toml')
        if not path.exists(metadata):
            remote = get_remote_url(opts.spell)
            if remote is not None:
                print("Downloading spell from: {}".format(remote))
                download(remote, spell_dir)
            else:
                print("Could not find spell: {}".format(spell))
                sys.exit(1)
        else:
            with open(metadata) as fp:
                metadata = toml.loads(fp.read())

    app = Application(opts, spell, metadata)
    app.start()
