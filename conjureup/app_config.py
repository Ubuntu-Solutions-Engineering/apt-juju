""" application config
"""
import json
from types import SimpleNamespace

bootstrap = SimpleNamespace(
    # Is bootstrap running
    running=False,

    # Attached output
    output=None
)

maas = SimpleNamespace(
    # Client
    client=None,

    # API key
    api_key=None,

    # API Endpoint
    endpoint=None
)

juju = SimpleNamespace(
    # Client
    client=None,

    # Is authenticated?
    authenticated=False
)


class AppConfig:
    """ Application config storage
    """

    # Juju bootstrap details
    bootstrap = bootstrap

    # MAAS client
    maas = maas

    # Juju Client
    juju = juju

    # The conjure-up UI framework
    ui = None

    # Contains metadata and spell name
    config = None

    # List of multiple bundles, usually from a charmstore search
    bundles = None

    # Selected bundle from a Variant view
    current_bundle = None

    # cli opts
    argv = None

    # Is JAAS supported by the current spell
    jaas_ok = True

    # Which controller, if any, is the JAAS controller
    jaas_controller = None

    # Whether the JAAS controller is selected
    is_jaas = False

    current_model = None

    # Current Juju controller selected
    current_controller = None

    # Current Juju cloud selected
    current_cloud = None

    # Current Juju cloud type selected
    current_cloud_type = None

    # Current Juju cloud region
    current_region = None

    # Current UI View rendered
    current_view = None

    # Session ID for current deployment
    session_id = None

    # Application logger
    log = None

    # Charm store metadata API client
    metadata_controller = None

    # disable telemetry tracking
    notrack = False

    # disable automatic error reporting
    noreport = False

    # Application environment passed to processing steps
    env = None

    # Did deployment complete
    complete = False

    # Run in non interactive mode
    headless = False

    # Remote endpoint type (An enum, see download.py)
    endpoint_type = None

    # Reference to asyncio loop so that it can be accessed from other threads
    loop = None

    # Redis State storage endpoint
    state = None

    # exit code for conjure-up to terminate with
    exit_code = 0

    @property
    def _redis_key(self):
        """ Internal, formatted redis namespace key
        """
        return "conjure-up.{}.{}.{}".format(self.config['spell'],
                                            self.current_controller,
                                            self.current_model)

    def to_json(self):
        """
        Serialize application config to JSON

        We blacklist several items as they are intended to be reloaded during
        every invocation of conjure-up. Also blacklist env for security
        precautions.
        """
        blacklist = ['loop', 'log', 'maas',
                     'juju', 'ui', 'bootstrap',
                     'metadata_controller', 'state',
                     'env']
        new_dict = {}
        for k, v in self.__dict__.items():
            if k.startswith('__') or callable(getattr(self, k)):
                continue
            if k in blacklist:
                continue
            new_dict[k] = v
        return json.dumps(new_dict)

    def from_json(self, data):
        """ Deserializes application state and updates app_config
        """
        state = json.loads(data.decode('utf8'))
        for k, v in state.items():
            try:
                getattr(self, k)
            except AttributeError:
                continue
            setattr(self, k, v)

    async def save(self):
        self.log.info('Storing conjure-up state')
        if self.juju.is_authenticated:
            await self.juju.client.set_config(
                {'extra-info': self.to_json()})
            self.log.info('State saved in model config')
            # Check for existing redis key and clear it
            self.state.delete(self._redis_key)
        else:
            self.state.set(self._redis_key, self.to_json())
            self.log.info('State saved in redis')

    async def restore(self):
        self.log.info('Attempting to load conjure-up cached state.')
        try:
            if self.juju.is_authenticated:
                result = await self.juju.client.get_config()
                if 'extra-info' in result:
                    self.log.info(
                        "Found cached state from Juju model, reloading.")
                    self.from_json(result['extra-info'].value)
                    return
            result = self.state.get(self._redis_key)
            if result:
                self.log.info("Found cached state in Redis, reloading.")
                self.from_json(result.decode('utf8'))
        except json.JSONDecodeError as e:
            # Dont fail fatally if state information is incorrect. Just log it
            # and move on
            self.log.debug(
                "State information possibly corrupt "
                "or malformed: {}".format(e))


app = AppConfig()
