from urwid import Columns, Filler, Frame, Pile, Text, WidgetWrap

from conjureup.app_config import app
from ubuntui.utils import Color, Padding
from ubuntui.widgets.buttons import menu_btn
from ubuntui.widgets.hr import HR
from ubuntui.widgets.input import StringEditor


class NewCloudView(WidgetWrap):

    def __init__(self, schema, cb):
        self.input_items = schema
        self.cb = cb
        self.frame = Frame(body=self._build_widget(),
                           footer=self._build_footer())
        self.buttons_selected = False
        super().__init__(self.frame)

    def _build_widget(self):
        total_items = [Text(
            "Enter your {} credentials:".format(app.current_cloud.upper()))]
        total_items += [HR()]
        for k in self.input_items.keys():
            display = k
            if k.startswith('_'):
                # Don't treat 'private' keys as input
                continue
            if k.startswith('@'):
                # Strip public, not storable attribute
                display = k[1:]
            col = Columns(
                [
                    ('weight', 0.5, Text(display, align='right')),
                    Color.string_input(self.input_items[k],
                                       focus_map='string_input focus')
                ], dividechars=1
            )
            total_items.append(col)
            total_items.append(Padding.line_break(""))
        total_items.append(Text(""))
        self.pile = Pile(total_items)
        return Padding.center_60(Filler(self.pile, valign="top"))

    def _build_footer(self):
        cancel = menu_btn(on_press=self.cancel,
                          label="\n  BACK\n")
        confirm = menu_btn(on_press=self.submit,
                           label="\n ADD CREDENTIAL\n")
        self.buttons = Columns([
            ('fixed', 2, Text("")),
            ('fixed', 13, Color.menu_button(
                cancel,
                focus_map='button_primary focus')),
            Text(""),
            ('fixed', 20, Color.menu_button(
                confirm,
                focus_map='button_primary focus')),
            ('fixed', 2, Text(""))
        ])

        footer = Color.frame_footer(Pile([
            Padding.line_break(""),
            self.buttons
        ]))
        return footer

    def _swap_focus(self):
        if not self.buttons_selected:
            self.buttons_selected = True
            self.frame.focus_position = 'footer'
            self.buttons.focus_position = 3
        else:
            self.buttons_selected = False
            self.frame.focus_position = 'body'

    def keypress(self, size, key):
        if key in ['tab', 'shift tab']:
            self._swap_focus()
        rv = super().keypress(size, key)
        return rv

    def validate(self):
        """ Will provide an error text if any fields are blank
        """
        values = [i.value for i in self.input_items.values()
                  if isinstance(i, StringEditor)]

        if None in values:
            self.pile.contents[-1] = (
                Padding.center_60(
                    Color.error_major(
                        Text("Please fill all required fields."))),
                self.pile.options())
            return False
        return True

    def cancel(self, btn):
        self.cb(back=True)

    def submit(self, result):
        if self.validate():
            self.cb(self.input_items)
