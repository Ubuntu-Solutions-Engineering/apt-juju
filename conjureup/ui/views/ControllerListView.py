from collections import defaultdict

from ubuntui.utils import Color, Padding
from ubuntui.widgets.hr import HR
from urwid import Text

from conjureup.ui.views.base import BaseView
from conjureup.ui.widgets.selectors import MenuSelectButtonList


class ControllerListView(BaseView):
    title = 'Choose a Controller'
    subtitle = ('Please select an existing controller,'
                ' or choose to bootstrap a new one.')
    footer = ('The controller is what allows Juju to deploy and manage your '
              'models/spells.  With JaaS, the controller will be managed '
              'for you for free, so that you can focus on your applications '
              'and solutions. Alternatively, you can host and manage your own '
              'controller on the cloud to which you deploy.')

    def __init__(self, app, controllers, submit_cb, back_cb):
        self.app = app
        self.submit_cb = submit_cb
        self.prev_screen = back_cb
        self.controllers = controllers
        self.config = self.app.config
        super().__init__()

    def build_widget(self):
        widget = MenuSelectButtonList()
        if self.app.jaas_ok:
            widget.append_option('Juju-as-a-Service (JaaS) '
                                 'Free Controller', 'jaas')
        if len(self.controllers) > 0:
            if self.app.jaas_ok:
                widget.append(HR())
            widget.append(Color.label(Text(
                "Existing Self-Hosted Controllers")))
            widget.append(Padding.line_break(""))
            cdict = defaultdict(lambda: defaultdict(list))
            for cname, d in self.controllers.items():
                cdict[d['cloud']][d.get('region', None)].append(cname)

            for cloudname, cloud_d in sorted(cdict.items()):
                widget.append(Color.label(Text("  {}".format(cloudname))))
                for regionname, controllers in cloud_d.items():
                    for controller in sorted(controllers):
                        label = "    {}".format(controller)
                        if regionname:
                            label += " ({})".format(regionname)
                        widget.append_option(label, controller)
                widget.append(Padding.line_break(""))
            widget.append(Padding.line_break(""))
        widget.append(HR())
        widget.append_option("Deploy New Self-Hosted Controller", None)
        widget.select_first()
        return widget

    def submit(self):
        self.submit_cb(self.widget.selected)
