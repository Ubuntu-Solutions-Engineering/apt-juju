from conjure import controllers
from conjure import juju
from conjure import utils
from conjure.app_config import app
from . import common
import petname
import sys
import os


def finish():
    if app.argv.cloud == "localhost":
        if not utils.check_bridge_exists():
            back = "{} to localhost".format(app.argv.config['spell'])
            os.execl("/usr/share/conjure-up/run-lxd-config",
                     "/usr/share/conjure-up/run-lxd-config",
                     back)

    existing_controller = common.get_controller_in_cloud(app.argv.cloud)
    if existing_controller is None:
        return controllers.use('newcloud').render(app.argv.cloud)

    app.current_controller = existing_controller
    juju.switch_controller(app.current_controller)
    app.current_model = petname.Name()
    utils.info("Creating new juju model named '{}', "
               "please wait.".format(app.current_model))
    juju.add_model(app.current_model)
    juju.switch_model(app.current_model)

    return controllers.use('variants').render()


def render():
    if app.argv.cloud not in juju.get_clouds().keys():
        formatted_clouds = ", ".join(juju.get_clouds().keys())
        utils.warning("Unknown Cloud: {}, please choose "
                      "from one of the following: {}".format(app.argv.cloud,
                                                             formatted_clouds))
        sys.exit(1)
    utils.info(
        "Summoning {} to {}".format(app.argv.spell, app.argv.cloud))
    finish()
