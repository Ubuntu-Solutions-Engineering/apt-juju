""" Application Configuration View

"""

from juju.constraints import normalize_key
from juju.constraints import parse as parse_constraints
from ubuntui.widgets.hr import HR
from urwid import Columns, Text

from conjureup import consts, utils
from conjureup.app_config import app
from conjureup.ui.views.base import BaseView
from conjureup.ui.widgets.buttons import SecondaryButton
from conjureup.ui.widgets.option_widget import OptionWidget


class ApplicationConfigureView(BaseView):
    metrics_title = 'Configure Application'

    def __init__(self, application, close_cb):
        self.title = "Configure {}".format(application.name)
        self.application = application
        self.prev_screen = close_cb
        self.options_copy = self.application.options.copy()
        self.num_units_copy = self.application.num_units
        self.constraints_copy = self.application.constraints
        self.constraints_error_label = Text(('body', ''))
        self.showing_all = False
        super().__init__()

    def set_constraints_error(self, msg=None):
        if not msg:
            msg = (
                "Invalid constraints given, your choices are '{}'".format(
                    ", ".join(consts.ALLOWED_CONSTRAINTS)))
        self.constraints_error_label.set_text(('error_major', msg))

    def clear_constraints_error(self):
        self.constraints_error_label.set_text(('body', ''))

    def build_widget(self):
        app.loop.create_task(self._build_widget())
        return []

    async def _build_widget(self):
        ws = []
        if not self.application.is_subordinate:
            ws.append(OptionWidget("Units", "int",
                                   "How many units to deploy.",
                                   self.application.num_units,
                                   current_value=self.num_units_copy,
                                   value_changed_callback=self.handle_scale))

        constraints_ow = OptionWidget(
            "Constraints", "string",
            "Set constraints on the application, ie. cores=4 mem=4G.",
            self.application.constraints,
            current_value=self.constraints_copy,
            value_changed_callback=self.handle_constraints)
        ws.append(constraints_ow)
        ws.append(self.constraints_error_label)

        ws += await self.get_whitelisted_option_widgets()
        self.toggle_show_all_button_index = len(ws) + 1
        self.toggle_show_all_button = SecondaryButton(
            "Show Advanced Configuration",
            lambda sender: app.loop.create_task(
                self.do_toggle_show_all_config()))
        if await self.get_non_whitelisted_option_widgets():
            ws += [HR(),
                   Columns([('weight', 1, Text(" ")),
                            (36, self.toggle_show_all_button)])]
        for widget in ws:
            self.widget.contents.append((widget,
                                         self.widget.options()))

    def build_buttons(self):
        return [self.button('APPLY CHANGES', self.submit)]

    async def get_whitelisted_option_widgets(self):
        options = await app.juju.charmstore.config(self.application.charm)

        svc_opts_whitelist = utils.get_options_whitelist(
            self.application.name)
        hidden = [n for n in options['Options'].keys()
                  if n not in svc_opts_whitelist]
        app.log.info("Hiding options not in the whitelist: {}".format(hidden))

        return self._get_option_widgets(svc_opts_whitelist, options['Options'])

    async def get_non_whitelisted_option_widgets(self):
        options = await app.juju.charmstore.config(self.application.charm)

        svc_opts_whitelist = utils.get_options_whitelist(
            self.application.name)
        hidden = [n for n in options['Options'].keys()
                  if n not in svc_opts_whitelist]
        return self._get_option_widgets(hidden, options['Options'])

    def _get_option_widgets(self, opnames, options):
        ws = []
        for opname in opnames:
            try:
                opdict = options[opname]
            except KeyError:
                app.log.debug(
                    "Unknown charm option ({}), skipping".format(opname))
                continue
            cv = self.application.options.get(opname, None)
            ow = OptionWidget(opname,
                              opdict['Type'],
                              opdict['Description'],
                              opdict['Default'],
                              current_value=cv,
                              value_changed_callback=self.handle_edit)
            ws.append(ow)
        return ws

    async def do_toggle_show_all_config(self):
        if not self.showing_all:
            new_ows = await self.get_non_whitelisted_option_widgets()
            header = Text("Advanced Configuration Options")
            opts = self.widget.options()
            self.widget.contents.append((header, opts))
            for ow in new_ows:
                self.widget.contents.append((ow, opts))
            self.toggle_show_all_button.set_label(
                "Hide Advanced Configuration")
            self.showing_all = True
        else:
            i = self.toggle_show_all_button_index
            self.widget.contents = self.widget.contents[:i + 1]
            self.toggle_show_all_button.set_label(
                "Show Advanced Configuration")
            self.showing_all = False

    def handle_edit(self, opname, value):
        self.options_copy[opname] = value

    def handle_scale(self, opname, scale):
        self.num_units_copy = scale

    def handle_constraints(self, opname, constraint):
        self.constraints_copy = constraint

    def submit(self):
        if self.constraints_copy:
            try:
                parsed = set(parse_constraints(self.constraints_copy))
            except ValueError:
                return self.set_constraints_error()
            has_valid_constraints = parsed.issubset(
                {normalize_key(field) for field in consts.ALLOWED_CONSTRAINTS})
            if not has_valid_constraints:
                return self.set_constraints_error()

        self.application.options = self.options_copy
        self.application.num_units = self.num_units_copy
        self.application.constraints = self.constraints_copy
        # Replace application data with updated info
        new_data = self.application.to_dict()
        app.current_bundle['applications'][self.application.name] = new_data

        self.prev_screen()
