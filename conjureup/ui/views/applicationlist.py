""" Application List view

"""
from urwid import Columns, Text

from conjureup.app_config import app
from conjureup.ui.views.base import BaseView
from conjureup.ui.widgets.base import ContainerWidgetWrap
from conjureup.ui.widgets.buttons import SecondaryButton

readme_cache = {}


class ApplicationWidget(ContainerWidgetWrap):

    def __init__(self, application, maxlen, config_cb, arch_cb):
        self.application = application
        self._callbacks = {
            'config': config_cb,
            'arch': arch_cb,
        }
        self._selectable = True
        super().__init__(self.build_widgets(maxlen))
        self.columns.focus_position = len(self.columns.contents) - 1

    def __repr__(self):
        return "<ApplicationWidget for {}>".format(
            self.application)

    def selectable(self):
        return self._selectable

    def update_units(self):
        self.unit_w.set_text("Units: {:>4}".format(self.application.num_units))

    def build_widgets(self, maxlen):
        num_str = "{}".format(self.application.num_units)
        col_pad = 6
        self.unit_w = Text('Units: {:4d}'.format(self.application.num_units),
                           align='right')
        cws = [
            (maxlen + col_pad, Text(self.application.name)),
            (10 + len(num_str), self.unit_w),
            ('weight', 1, Text(" ")),  # placeholder for instance type
            (20, SecondaryButton("Configure", self._cb('config'))),
            (20, Text(" ")),  # placeholder for architecture button
        ]

        if self.application.num_units > 0:
            cws[4] = (20, SecondaryButton("Architect", self._cb('arch')))

        self.columns = Columns(cws, dividechars=1)
        return self.columns

    def _cb(self, cb_name):
        return lambda _: self._callbacks[cb_name](self.application)

    def remove_buttons(self):
        self._selectable = False
        self.columns.contents = self.columns.contents[:-3]


class ApplicationListView(BaseView):
    title = "Configure Applications"
    subtitle = ""  # set by __init__
    footer = ""  # set by after_keypress
    footer_align = "left"

    def __init__(self, applications, config_cb, arch_cb, finish_cb, back_cb):
        self.subtitle = "{} Applications in {}:".format(len(applications),
                                                        app.config['spell'])
        self.applications = applications
        self._config_cb = config_cb
        self._arch_cb = arch_cb
        self.prev_screen = back_cb
        self.finish_cb = finish_cb

        for application in self.applications:
            if application.name not in readme_cache:
                readme_cache[application.charm] = 'Loading README...'
                app.loop.create_task(self._load_readme(application.charm))

        super().__init__()
        self.after_keypress()  # force footer update

    def build_widget(self):
        ws = []
        max_app_name_len = max(
            [len(app.name) for app in self.applications])
        for application in self.applications:
            ws.append(Text(""))
            ws.append(ApplicationWidget(application,
                                        max_app_name_len,
                                        self._config_cb,
                                        self._arch_cb))
        return ws

    def build_buttons(self):
        label = 'DEPLOY'
        return [self.button(label, self.submit)]

    def after_keypress(self):
        "Check if focused widget changed, then update readme."
        fw = self.widget.focus
        if not isinstance(fw, ApplicationWidget):
            self.set_footer("No selected application")
        else:
            self.set_footer(self.get_readme(fw.application.charm))

    def get_readme(self, application):
        return readme_cache[application]

    async def _load_readme(self, charm):
        readme = await app.juju.charmstore.entity_readme_content(charm)
        readme_cache[charm] = self._trim_readme(readme)
        self.after_keypress()  # update loading message if currently displayed

    def _trim_readme(self, readme):
        rls = readme.splitlines()
        rls = [l for l in rls if not l.startswith("#")]
        nrls = []
        for i in range(len(rls)):
            if i + 1 == len(rls):
                break
            if len(rls[i]) > 0:
                if rls[i][0] in ['-', '#', '=']:
                    continue
            if len(rls[i + 1]) > 0:
                if rls[i + 1][0] in ['-', '=']:
                    continue
            nrls.append(rls[i])

        if len(nrls) == 0:
            return

        if nrls[0] == '':
            nrls = nrls[1:]
        # split after two paragraphs:
        if '' in nrls:
            firstparidx = nrls.index('')
        else:
            firstparidx = 1
        try:
            splitidx = nrls.index('', firstparidx + 1)
        except:
            splitidx = firstparidx
        nrls = nrls[:splitidx]
        return "\n".join(nrls)

    def update_units(self):
        for app_w, opts in self.widget.contents:
            if isinstance(app_w, ApplicationWidget):
                app_w.update_units()

    def _widget_for(self, application):
        for w, o in self.widget.contents:
            if getattr(w, 'application', None) is application:
                return w

    def submit(self):
        self.finish_cb()
