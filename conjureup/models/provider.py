from collections import OrderedDict
from functools import partial

from urwid import Text

from ubuntui.widgets.input import PasswordEditor, StringEditor, YesNo


""" Defining the schema

The schema contains attributes for rendering proper credentials.

A typical schema is:

'auth-type': 'access-key' - defines the auth type supported by provider
'fields': [] - editable fields in the ui, each field can contain:
  'label'    - Friendly label to the user
  'widget'   - Input widget
  'key'      - key that matches what the provider expects for authentication
  'storable' - if False will skip storing key=value in credentials
  'validator'- Function to check validity, returns (Boolean, "Optional error")
"""


class Field:
    """ Field class with validation
    """

    def __init__(self,
                 label=None,
                 widget=None,
                 key=None,
                 storable=True,
                 error=None,
                 required=True,
                 validator=None):
        self.label = label
        self.widget = widget
        self.key = key
        self.storable = storable
        self.error = Text("")
        self.required = required
        self.validator = validator

    def validate(self):
        """ Validator for field
        """
        self.error.set_text("")

        if self.required and not self.value:
            self.error.set_text("This field is required and cannot be empty.")
            return False
        if self.validator and callable(self.validator):
            is_valid, msg = self.validator()
            if not is_valid:
                self.error.set_text(msg)
                return False
        return True

    @property
    def value(self):
        return self.widget.value


class BaseProvider:
    """ Base provider for all schemas
    """
    AUTH_TYPE = None

    def is_valid(self):
        validations = []
        for f in self.fields():
            validations.append(f.validate())

        if not all(validations):
            return False
        return True

    def fields(self):
        raise NotImplementedError


class AWS(BaseProvider):
    AUTH_TYPE = 'access-key'
    ACCESS_KEY = Field(label='AWS Access Key',
                       widget=StringEditor(),
                       key='access-key')
    SECRET_KEY = Field(label='AWS Secret Key',
                       widget=StringEditor(),
                       key='secret-key'),

    def fields(self):
        return [
            self.ACCESS_KEY,
            self.SECRET_KEY
        ]


class MAAS(BaseProvider):
    AUTH_TYPE = 'oauth1'

    def __init__(self):
        self.address = Field(
            label='server address (only the ip or dns name)',
            widget=StringEditor(),
            key='endpoint',
            storable=False
        )
        self.apikey = Field(
            label='api key',
            widget=StringEditor(),
            key='maas-oauth',
            validator=partial(self._has_correct_api_key)
        )

    def fields(self):
        return [
            self.address,
            self.apikey
        ]

    def _has_correct_api_key(self):
        """ Validates MAAS Api key
        """
        key = self.apikey.value.split(':')
        if len(key) != 3:
            return (
                False,
                "Could not determine tokens, usually indicates an "
                "error with the format of the API KEY. That format "
                "should be 'aaaaa:bbbbb:cccc'. Please visit your MAAS user "
                "preferences page to grab the correct API Key: "
                "http://<maas-server>:5240/MAAS/account/prefs/")
        return (True, None)


class Azure(BaseProvider):
    AUTH_TYPE = 'service-principal-secret'

    def __init__(self):
        self.application_id = Field(
            label='application id',
            widget=StringEditor(),
            key='application-id'
        )
        self.subscription_id = Field(
            label='subscription id',
            widget=StringEditor(),
            key='subscription-id'
        )
        self.tenant_id = Field(
            label='tenant id',
            widget=StringEditor(),
            key='tenant-id'
        )
        self.application_password = Field(
            label='application password',
            widget=PasswordEditor(),
            key='application-password'
        )

    def fields(self):
        return [
            self.application_id,
            self.subscription_id,
            self.tenant_id,
            self.application_password
        ]


class Google(BaseProvider):
    AUTH_TYPE = 'oauth2'

    def __init__(self):
        self.private_key = Field(
            label='private key',
            widget=StringEditor(),
            key='private-key'
        )
        self.client_id = Field(
            label='private key',
            widget=StringEditor(),
            key='client-id'
        )
        self.client_email = Field(
            label='client email',
            widget=StringEditor(),
            key='client-email'
        )
        self.project_id = Field(
            label='project id',
            widget=StringEditor(),
            key='project-id'
        )

    def fields(self):
        return [
            self.private_key,
            self.client_id,
            self.client_email,
            self.project_id
        ]


class CloudSigma(BaseProvider):
    AUTH_TYPE = 'userpass'

    def __init__(self):
        self.username = Field(
            label='username',
            widget=StringEditor(),
            key='username'
        )
        self.password = Field(
            label='password',
            widget=StringEditor(),
            key='password'
        )

    def fields(self):
        return [
            self.username,
            self.password
        ]


class Joyent(BaseProvider):
    AUTH_TYPE = 'userpass'

    def __init__(self):
        self.sdc_user = Field(
            label='sdc user',
            widget=StringEditor(),
            key='sdc-user'
        )
        self.sdc_key_id = Field(
            label='sdc key id',
            widget=StringEditor(),
            key='sdc-key-id'
        )
        self.private_key = Field(
            label='private key',
            widget=StringEditor(),
            key='private-key'
        )
        self.algorithm = Field(
            label='algorithm',
            widget=StringEditor(default='rsa-sha256'),
            key='algorithm'
        )

    def fields(self):
        return [
            self.sdc_user,
            self.sdc_key_id,
            self.private_key,
            self.algorithm
        ]


class OpenStack(BaseProvider):
    AUTH_TYPE = 'userpass'

    def __init__(self):
        self.username = Field(
            label='username',
            widget=StringEditor(),
            key='username'
        )
        self.password = Field(
            label='password',
            widget=PasswordEditor(),
            key='password'
        )
        self.domain_name = Field(
            label='domain name',
            widget=StringEditor(),
            key='domain-name'
        )
        self.project_domain_name = Field(
            label='project domain name',
            widget=StringEditor(),
            key='project-domain-name'
        )
        self.access_key = Field(
            label='access key',
            widget=StringEditor(),
            key='access-key'
        )
        self.secret_key = Field(
            label='secret key',
            widget=StringEditor(),
            key='secret-key'
        )

    def fields(self):
        return [
            self.username,
            self.password,
            self.domain_name,
            self.project_domain_name,
            self.access_key,
            self.secret_key,
        ]


class VSphere(BaseProvider):
    AUTH_TYPE = 'userpass'

    def __init__(self):
        self.api_endpoint = Field(
            label='api endpoint',
            widget=StringEditor(),
            key='endpoint',
            storable=False
        )
        self.user = Field(
            label='user',
            widget=StringEditor(),
            key='user'
        )
        self.password = Field(
            label='password',
            widget=PasswordEditor(),
            key='password'
        )
        self.external_network = Field(
            label='external network',
            widget=StringEditor(),
            key='external-network',
            storable=False
        )

    def fields(self):
        return [
            self.api_endpoint,
            self.user,
            self.password,
            self.external_network
        ]


Schema = [
    ('aws', AWS),
    ('aws-china', AWS),
    ('aws-gov', AWS),
    ('maas', MAAS),
    ('azure', Azure),
    ('azure-china', Azure),
    ('google', Google),
    ('cloudsigma', CloudSigma),
    ('joyent', Joyent),
    ('openstack', OpenStack),
    ('rackspace', OpenStack),
    ('vsphere', VSphere)
]


def load_schema(cloud):
    """ Loads a schema
    """
    for s in Schema:
        k, v = s
        if cloud == k:
            return v()
    raise Exception("Could not find schema for: {}".format(cloud))


SchemaV1 = OrderedDict([
    ('aws', OrderedDict([
        ('_auth-type', 'access-key'),
        ('access-key', StringEditor()),
        ('secret-key', StringEditor())
    ])),
    ('aws-china', OrderedDict([
        ('_auth-type', 'access-key'),
        ('access-key', StringEditor()),
        ('secret-key', StringEditor())
    ])),
    ('aws-gov', OrderedDict([
        ('_auth-type', 'access-key'),
        ('access-key', StringEditor()),
        ('secret-key', StringEditor())
    ])),
    ('maas', OrderedDict([
        ('_auth-type', 'oauth1'),
        ('@maas-server', StringEditor()),
        ('maas-oauth', StringEditor())
    ])),
    ('azure', OrderedDict([
        ('_auth-type', 'userpass'),
        ('application-id', StringEditor()),
        ('subscription-id', StringEditor()),
        ('tenant-id', StringEditor()),
        ('application-password', PasswordEditor()),
        ('location', StringEditor()),
        ('endpoint', StringEditor()),
        ('storage-endpoint', StringEditor()),
        ('storage-account-type', StringEditor()),
        ('storage-account', StringEditor()),
        ('storage-account-key', StringEditor()),
        ('controller-resource-group', StringEditor())
    ])),
    ('azure-china', OrderedDict([
        ('_auth-type', 'userpass'),
        ('application-id', StringEditor()),
        ('subscription-id', StringEditor()),
        ('tenant-id', StringEditor()),
        ('application-password', PasswordEditor()),
        ('location', StringEditor()),
        ('endpoint', StringEditor()),
        ('storage-endpoint', StringEditor()),
        ('storage-account-type', StringEditor()),
        ('storage-account', StringEditor()),
        ('storage-account-key', StringEditor()),
        ('controller-resource-group', StringEditor())
    ])),
    ('google', OrderedDict([
        ('private-key', StringEditor()),
        ('client-id', StringEditor()),
        ('client-email', StringEditor()),
        ('region', StringEditor()),
        ('project-id', StringEditor()),
        ('image-endpoint', StringEditor())
    ])),
    ('cloudsigma', OrderedDict([
        ('username', StringEditor()),
        ('password', PasswordEditor()),
        ('region', StringEditor()),
        ('endpoint', StringEditor())
    ])),
    ('joyent', OrderedDict([
        ('sdc-user', StringEditor()),
        ('sdc-key-id', StringEditor()),
        ('sdc-url', StringEditor(
            default='https://us-west-1.api.joyentcloud.com')),
        ('private-key-path', StringEditor()),
        ('algorithm', StringEditor(default='rsa-sha256'))
    ])),
    ('openstack', OrderedDict([
        ('_auth-type', 'userpass'),
        ('username', StringEditor()),
        ('password', PasswordEditor()),
        ('tenant-name', StringEditor()),
        ('auth-url', StringEditor()),
        ('auth-mode', StringEditor()),
        ('access-key', StringEditor()),
        ('secret-key', StringEditor()),
        ('region', StringEditor()),
        ('use-floating-ip', YesNo()),
        ('use-default-secgroup', YesNo()),
        ('network', StringEditor())
    ])),
    ('rackspace', OrderedDict([
        ('_auth-type', 'userpass'),
        ('username', StringEditor()),
        ('password', PasswordEditor()),
        ('tenant-name', StringEditor()),
        ('auth-url', StringEditor()),
        ('auth-mode', StringEditor()),
        ('access-key', StringEditor()),
        ('secret-key', StringEditor()),
        ('region', StringEditor()),
        ('use-floating-ip', YesNo()),
        ('use-default-secgroup', YesNo()),
        ('network', StringEditor())
    ])),
    ('vsphere', OrderedDict([
        ('_auth-type', 'userpass'),
        ('host', ("vcenter api-endpoint", StringEditor())),
        ('user', ("vcenter username", StringEditor())),
        ('password', ("vcenter password", PasswordEditor())),
        ('regions', ("datacenter", StringEditor())),
        ('external-network', StringEditor())
    ])),
    ('manual', OrderedDict([
        ('bootstrap-host', StringEditor()),
        ('bootstrap-user', StringEditor()),
        ('use-sshstorage', YesNo())
    ])),
])
