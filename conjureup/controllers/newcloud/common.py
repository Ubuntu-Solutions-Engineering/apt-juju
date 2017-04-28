import os
import os.path as path
from pathlib import Path
from subprocess import DEVNULL, CalledProcessError

import yaml

from conjureup import juju, utils
from conjureup.app_config import app
from conjureup.telemetry import track_event

cred_path = path.join(utils.juju_path(), 'credentials.yaml')


def __format_creds(creds):
    """ Formats the credentials into strings from the widgets values
    """
    formatted = {}
    formatted['auth-type'] = creds.AUTH_TYPE
    for field in creds.fields():
        if not field.storable:
            continue
        formatted[field.key] = field.value

    return formatted


def try_get_creds(cloud):
    """ Check if credentials for existing cloud already exists so
    we can bypass the cloud config view and go straight to bootstrapping

    Arguments:
    cloud: public cloud

    Returns:
    First set of credentials found for cloud
    """
    if not path.isfile(cred_path):
        return None

    existing_creds = yaml.safe_load(open(cred_path))
    if 'credentials' not in existing_creds:
        return None

    if cloud not in existing_creds['credentials'].keys():
        return None

    if len(existing_creds['credentials'][cloud].keys()) == 0:
        return None

    if 'default-credential' in existing_creds['credentials'][cloud]:
        return existing_creds['credentials'][cloud]['default-credential']

    # XXX we should really prompt to select because this is non-deterministic
    for k, v in existing_creds['credentials'][cloud].items():
        if 'default-region' in k:
            app.current_region = v
        else:
            return k


def save_creds(cloud, credentials):
    """ stores credentials for cloud
    """
    try:
        existing_creds = yaml.safe_load(open(cred_path))
    except:
        existing_creds = {'credentials': {}}

    if cloud in existing_creds['credentials'].keys():
        c = existing_creds['credentials'][cloud]
        c[app.current_controller] = __format_creds(
            credentials)
    else:
        # Handle the case where path exists but an entry for the cloud
        # has yet to be added.
        existing_creds['credentials'][cloud] = {
            app.current_controller: __format_creds(
                credentials)
        }

    with open(cred_path, 'w') as cred_f:
        cred_f.write(yaml.safe_dump(existing_creds,
                                    default_flow_style=False))


def is_lxd_ready():
    """ routine for making sure lxd is configured for localhost deployments
    """
    if not utils.check_user_in_group('lxd'):
        return {"ready": False,
                "msg": "User {} is not part of the LXD group. You will need "
                "to exit conjure-up and do one of the following:\n\n"
                " 1: Run `newgrp lxd` and re-launch conjure-up\n\n"
                "  Or\n\n"
                " 2: Log out completely, Log in and "
                "re-launch conjure-up".format(os.environ['USER'])}

    try:
        lxd_init()
        setup_conjureup1_network()
        setup_conjureup0_network()
    except Exception as e:
        return {"ready": False,
                "msg": "Unable to determine an existing LXD network bridge, "
                "please make sure you've run `sudo lxd init` to configure "
                "LXD.\n\n{}".format(e)}

    if utils.lxd_has_ipv6():
        return {"ready": False,
                "msg": "The LXD bridge has IPv6 enabled. Currently this is "
                "unsupported by conjure-up. Please disable IPv6 and "
                "re-launch conjure-up\n\n"
                "Visit https://docs.ubuntu.com/conjure-up/en/troubleshoot#lxd "
                "for information on how to disable IPv6."}

    app.log.debug("Found an IPv4 address, "
                  "assuming LXD is configured.")
    return {"ready": True, "msg": ""}


def lxd_init():
    """ Runs initial lxd init
    """
    app.log.debug("Determining if embedded LXD is setup and ready.")
    snap_user_data = os.environ.get('SNAP_USER_DATA', None)
    if snap_user_data:
        lxd_setup_path = Path(snap_user_data) / 'lxd.setup'
        if not lxd_setup_path.exists():
            out = utils.run_script("lxc version")
            app.log.debug("Grabbing embedded LXC Version: {}".format(out))
            out = utils.run_script("lxd init --auto")
            app.log.debug("Initializing LXD: {}".format(out))
            out = utils.run_script(
                'lxc config set core.https_address [::]:12001')
            app.log.debug("Setting custom LXD Port: {}".format(out))
            out = utils.run_script(
                'lxc profile device add default eth0 nic nictype=bridged '
                'parent=conjureup1 name=eth0')
            app.log.debug(
                "Adding custom bridge to default profile: {}".format(out))
            lxd_setup_path.touch()


def setup_conjureup0_network():
    """ This attempts to setup LXD network bridge for conjureup if not available
    """
    out = utils.run_script('lxc network show conjureup0',
                           stdout=DEVNULL,
                           stderr=DEVNULL)
    if out.returncode != 0:
        out = utils.run_script('lxc network create conjureup0 '
                               'ipv4.address=10.99.0.1/24 '
                               'ipv4.nat=true '
                               'ipv6.address=none '
                               'ipv6.nat=false')
        if out.returncode != 0:
            raise Exception(
                "Failed to create LXD conjureup0 network bridge: {}".format(
                    out.stderr.decode()))


def setup_conjureup1_network():
    """ This attempts to setup LXD networking if not available
    """
    try:
        utils.run('lxc network show conjureup1', shell=True, check=True,
                  stdout=DEVNULL, stderr=DEVNULL)
    except CalledProcessError:
        out = utils.run_script('lxc network create conjureup1 '
                               'ipv4.address=10.100.0.1/24 '
                               'ipv4.nat=true '
                               'ipv6.address=none '
                               'ipv6.nat=false')
        if out.returncode != 0:
            raise Exception(
                "Failed to create LXD network bridge: {}".format(
                    out.stderr.decode()))
        utils.run_script(
            'lxc network attach-profile conjureup1 default eth0 eth0')
    out = utils.run_script(
        "lxc network show conjureup1 | grep -q 'ipv4\.address:\snone'")
    if out.returncode == 0:
        network_set_cmds = [
            'lxc network set conjureup1 ipv4.address 10.0.8.1/24',
            'lxc network set conjureup1 ipv4.nat true'
        ]
        for n in network_set_cmds:
            out = utils.run_script(n)
            if out.returncode != 0:
                raise Exception("Problem with {}: {}".format(
                    n, out.stderr.decode()))


async def do_bootstrap(creds, msg_cb, fail_msg_cb):
    if not app.is_jaas:
        app.log.info('Bootstrapping Juju controller.')
        msg_cb('Bootstrapping Juju controller.')
        track_event("Juju Bootstrap", "Started", "")
        cloud_with_region = app.current_cloud
        if app.current_region:
            cloud_with_region = '/'.join([app.current_cloud,
                                          app.current_region])
        success = await juju.bootstrap(app.current_controller,
                                       cloud_with_region,
                                       app.current_model,
                                       credential=creds)
        if not success:
            pathbase = os.path.join(
                app.config['spell-dir'],
                '{}-bootstrap').format(app.current_controller)
            with open(pathbase + ".err") as errf:
                err_log = "\n".join(errf.readlines())
            msg = "Error bootstrapping controller: {}".format(err_log)
            app.log.error(msg)
            fail_msg_cb(msg)
            cloud_type = juju.get_cloud_types_by_name()[app.current_cloud]
            raise Exception('Unable to bootstrap (cloud type: {})'.format(
                cloud_type))
            return

        app.log.info('Bootstrap complete.')
        msg_cb('Bootstrap complete.')
        track_event("Juju Bootstrap", "Done", "")

        await juju.login()  # login to the newly created (default) model

        # Set provider type for post-bootstrap
        app.env['JUJU_PROVIDERTYPE'] = app.juju.client.info.provider_type
        app.env['JUJU_CONTROLLER'] = app.current_controller
        app.env['JUJU_MODEL'] = app.current_model

        await utils.run_step('00_post-bootstrap',
                             'post-bootstrap',
                             msg_cb,
                             'Juju Post-Bootstrap')
    else:
        app.log.info('Adding new model in the background.')
        msg_cb('Adding new model in the background.')
        track_event("Juju Add JaaS Model", "Started", "")
        await juju.add_model(app.current_model,
                             app.current_controller,
                             app.current_cloud)
        track_event("Juju Add JaaS Model", "Done", "")
        app.log.info('Add model complete.')
        msg_cb('Add model complete.')
