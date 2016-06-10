""" Juju helpers
"""
from conjure import async
from conjure.utils import juju_path
from conjure.app_config import app
from bundleplacer.charmstore_api import CharmStoreID
from functools import wraps, partial
import macumba
from macumba.v2 import JujuClient
from subprocess import run, PIPE, DEVNULL, CalledProcessError
import os
import sys
import yaml


JUJU_ASYNC_QUEUE = "juju-async-queue"

this = sys.modules[__name__]

# vars
this.IS_AUTHENTICATED = False
this.CLIENT = None
this.USER_TAG = None


# login decorator
def requires_login(f):
    def _decorator(*args, **kwargs):
        if not this.IS_AUTHENTICATED:
            login()
        return f(*args, **kwargs)
    return wraps(f)(_decorator)


def read_config(name):
    """ Reads a juju config file

    Arguments:
    name: filename without extension (ext defaults to yaml)

    Returns:
    dictionary of yaml object
    """
    abs_path = os.path.join(juju_path(), "{}.yaml".format(name))
    if not os.path.isfile(abs_path):
        raise Exception("Cannot load {}".format(abs_path))
    return yaml.safe_load(open(abs_path))


def get_current_controller():
    """ Grabs the current default controller
    """
    try:
        return get_controllers()['current-controller']
    except KeyError:
        return None


def get_controller(id):
    """ Return specific controller

    Arguments:
    id: controller id
    """
    if 'controllers' in get_controllers() \
       and id in get_controllers()['controllers']:
        return get_controllers()['controllers'][id]
    return None


def login(force=False):
    """ Login to Juju API server
    """
    if not available():
        raise Exception("Tried to login to a non bootstrapped environment.")

    if this.IS_AUTHENTICATED is True and not force:
        return

    if not get_current_controller():
        raise Exception("Unable to determine current controller")

    env = get_controller(get_current_controller())
    account = get_account(get_current_controller())
    uuid = get_model(get_current_model())['model-uuid']
    server = env['api-endpoints'][0]
    this.USER_TAG = "user-{}".format(account['current'])
    current_user = account['current']
    password = account['users'][current_user]['password']
    url = os.path.join('wss://', server, 'model', uuid, 'api')
    this.CLIENT = JujuClient(
        user=this.USER_TAG,
        url=url,
        password=password)
    try:
        this.CLIENT.login()
    except macumba.errors.LoginError as e:
        raise e
    this.IS_AUTHENTICATED = True  # noqa


def bootstrap(controller, cloud, series="xenial", credential=None):
    """ Performs juju bootstrap

    If not LXD pass along the newly defined credentials

    Arguments:
    controller: name of your controller
    cloud: name of local or public cloud to deploy to
    series: define the bootstrap series defaults to xenial
    log: application logger
    credential: credentials key
    """
    cmd = "juju bootstrap {} {} --upload-tools " \
          "--config image-stream=daily ".format(
              controller, cloud)
    cmd += "--config enable-os-refresh-update=false "
    cmd += "--config enable-os-upgrade=false "
    cmd += "--bootstrap-series={} ".format(series)
    if cloud != "localhost":
        cmd += "--credential {}".format(credential)
    app.log.debug("bootstrap cmd: {}".format(cmd))
    try:
        return run(cmd, shell=True, stdout=DEVNULL, stderr=PIPE)
    except CalledProcessError:
        raise Exception("Unable to bootstrap.")


def bootstrap_async(controller, cloud, credential=None, exc_cb=None):
    """ Performs a bootstrap asynchronously
    """
    return async.submit(partial(bootstrap,
                                controller=controller,
                                cloud=cloud,
                                credential=credential), exc_cb,
                        queue_name=JUJU_ASYNC_QUEUE)


def available():
    """ Checks if juju is available

    Returns:
    True/False if juju status was successful and a environment is found
    """
    try:
        run('juju status', shell=True,
            check=True, stderr=DEVNULL, stdout=DEVNULL)
    except CalledProcessError:
        return False
    return True


def autoload_credentials():
    """ Automatically checks known places for cloud credentials
    """
    try:
        run('juju autoload-credentials', shell=True, check=True)
    except CalledProcessError:
        return False
    return True


def get_credential(cloud, user):
    """ Get credentials for user

    Arguments:
    cloud: cloud applicable to user credentials
    user: user listed in the credentials
    """
    creds = get_credentials()
    if cloud in creds.keys():
        if user in creds[cloud].keys():
            return creds[cloud][user]
    raise Exception(
        "Unable to locate credentials for: {}".format(user))


def get_credentials(secrets=True):
    """ List credentials

    This will fallback to reading the credentials file directly

    Arguments:
    secrets: True/False whether to show secrets (ie password)

    Returns:
    List of credentials
    """
    cmd = 'juju list-credentials --format yaml'
    if secrets:
        cmd += ' --show-secrets'
    sh = run(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    if sh.returncode > 0:
        try:
            env = read_config('credentials')
            return env['credentials']
        except:
            raise Exception(
                "Unable to list credentials: {}".format(
                    sh.stderr.decode('utf8')))
    env = yaml.safe_load(sh.stdout.decode('utf8'))
    return env['credentials']


def get_clouds():
    """ List available clouds

    Returns:
    Dictionary of all known clouds including newly created MAAS/Local
    """
    sh = run('juju list-clouds --format yaml',
             shell=True, stdout=PIPE, stderr=PIPE)
    if sh.returncode > 0:
        raise Exception(
            "Unable to list clouds: {}".format(sh.stderr.decode('utf8'))
        )
    return yaml.safe_load(sh.stdout.decode('utf8'))


def get_cloud(name):
    """ Return specific cloud information

    Arguments:
    name: name of cloud to query, ie. aws, lxd, local:provider
    Returns:
    Dictionary of cloud attributes
    """
    if name in get_clouds().keys():
        return get_clouds()[name]
    raise LookupError("Unable to locate cloud: {}".format(name))


def switch(model):
    """ Switch to a Juju Model

    Arguments:
    model: Model to select

    Returns:
    Raises exception if failed to switch models.
    """
    try:
        app.log.debug('switching to juju model: {}'.format(model))
        run('juju switch {}'.format(model),
            shell=True, check=True, stdout=DEVNULL, stderr=DEVNULL)
        login(True)
    except CalledProcessError as e:
        raise LookupError("Unable to switch models: {}".format(e))


def deploy(bundle):
    """ Juju deploy bundle

    Arguments:
    bundle: Name of bundle to deploy, can be a path to local bundle file or
            charmstore path.
    """
    try:
        return run('juju deploy {}'.format(bundle), shell=True,
                   stdout=DEVNULL, stderr=PIPE)
    except CalledProcessError as e:
        raise e


def deploy_service(service, msg_cb=None, exc_cb=None):
    """Juju deploy service.

    If the service's charm ID doesn't have a revno, will query charm
    store to get latest revno for the charm

    Arguments:
    service: Service to deploy
    msg_cb: message callback
    exc_cb: exception handler callback

    """
    if service.csid.rev == "":
        id_no_rev = service.csid.as_str_without_rev()
        mc = app.metadata_controller
        info = mc.get_charm_info(id_no_rev, lambda: None)
        service.csid = CharmStoreID(info["Id"])

    @requires_login
    def do_deploy():
        params = {"Applications": [service.as_deployargs()]}
        app.log.debug("Deploying {}: {}".format(service, params))
        try:
            deploy_message = "Deploying application: {}".format(
                service.service_name)
            if msg_cb:
                msg_cb("{}".format(deploy_message))
            this.CLIENT.Application(request="Deploy",
                                    params=params)
            if msg_cb:
                msg_cb("{}...done.".format(deploy_message))
        except Exception as e:
            if exc_cb:
                exc_cb(e)

    return async.submit(do_deploy,
                        exc_cb,
                        queue_name=JUJU_ASYNC_QUEUE)


def set_relations(services, msg_cb=None, exc_cb=None):
    """ Juju set relations

    Arguments:
    services: list of services with relations to set
    msg_cb: message callback
    exc_cb: exception handler callback
    """
    relations = set()
    for service in services:
        for a, b in service.relations:
            if (a, b) not in relations and (b, a) not in relations:
                relations.add((a, b))

    @requires_login
    def do_add_all():
        if msg_cb:
            msg_cb("Setting application relations")

        for a, b in list(relations):
            params = {"Endpoints": [a, b]}
            try:
                this.CLIENT.Application(request="AddRelation",
                                        params=params)
            except Exception as e:
                if exc_cb:
                    exc_cb(e)
                return
        if msg_cb:
            msg_cb("Completed setting application relations")

    return async.submit(do_add_all,
                        exc_cb,
                        queue_name=JUJU_ASYNC_QUEUE)


def get_controller_info(name=None):
    """ Returns information on current controller

    Arguments:
    name: if set shows info controller, otherwise displays current.
    """
    cmd = 'juju show-controller --format yaml'
    if name is not None:
        cmd += ' {}'.format(name)
    sh = run(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    if sh.returncode > 0:
        raise Exception(
            "Unable to determine controller: {}".format(
                sh.stderr.decode('utf8')))
    out = yaml.safe_load(sh.stdout.decode('utf8'))
    try:
        return next(iter(out.values()))
    except:
        return out


def get_controllers():
    """ List available controllers

    Returns:
    List of known controllers
    """
    sh = run('juju list-controllers --format yaml',
             shell=True, stdout=PIPE, stderr=PIPE)
    if sh.returncode > 0:
        raise LookupError(
            "Unable to list controllers: {}".format(sh.stderr.decode('utf8')))
    env = yaml.safe_load(sh.stdout.decode('utf8'))
    return env


def get_account(controller):
    """ List account information for controller

    Arguments:
    controller: controller id

    Returns:
    Dictionary containing list of accounts for controller and the
    current account in use.

    eg: {'users': [accounts], 'current': 'admin@local'}
    """
    account = {
        'users': None,
        'current': None
    }
    accounts = get_accounts()
    if accounts and controller in accounts:
        account['users'] = accounts[controller].get('accounts', [])
        account['current'] = accounts[controller].get(
            'current-account', None)
    return account


def get_accounts():
    """ List available accounts

    Returns:
    List of known accounts
    """
    env = os.path.join(juju_path(), 'accounts.yaml')
    if not os.path.isfile(env):
        raise Exception(
            "Unable to find: {}".format(env))
    with open(env, 'r') as c:
        env = yaml.load(c)
        return env['controllers']
    raise Exception("Unable to find accounts")


def model_by_owner(user):
    """ List model associated with user

    Arguments:
    user: username to query

    Returns:
    Dictionary containing model information for user
    """
    models = get_models()
    for m in models:
        if m['owner'] == user:
            return m
    raise LookupError(
        "Unable to find user: {}".format(
            user
        ))


def get_model(name):
    """ List information for model

    Arguments:
    name: model name

    Returns:
    Dictionary of model information
    """
    models = get_models()['models']
    for m in models:
        if m['name'] == name:
            return m
    raise LookupError(
        "Unable to find model: {}".format(name))


def add_model(name):
    """ Adds a model to current controller
    """
    sh = run('juju add-model {}'.format(name),
             shell=True, stdout=DEVNULL, stderr=PIPE)
    if sh.returncode > 0:
        raise Exception(
            "Unable to create model: {}".format(sh.stderr.decode('utf8')))


def get_models():
    """ List available models

    Returns:
    List of known models
    """
    sh = run('juju list-models --format yaml',
             shell=True, stdout=PIPE, stderr=PIPE)
    if sh.returncode > 0:
        raise LookupError(
            "Unable to list models: {}".format(sh.stderr.decode('utf8')))
    out = yaml.safe_load(sh.stdout.decode('utf8'))
    return out


def get_current_model():
    try:
        return get_models()['current-model']
    except:
        return None


def version():
    """ Returns version of Juju
    """
    sh = run('juju version', shell=True, stdout=PIPE, stderr=PIPE)
    if sh.returncode > 0:
        raise Exception(
            "Unable to get Juju Version".format(sh.stderr.decode('utf8')))
    out = sh.stdout.decode('utf8')
    if isinstance(out, list):
        return out.pop()
    else:
        return out
