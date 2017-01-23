from conjureup import async, controllers, juju, utils
from conjureup.app_config import app
from conjureup.telemetry import track_exception, track_screen
from conjureup.ui.views.ControllerListView import ControllerListView


class ControllerPicker:

    def __init__(self):
        self.view = None

    def __handle_exception(self, exc):
        track_exception(exc.args[0])
        app.ui.show_exception_message(exc)

    def __add_model(self):
        juju.add_model(app.current_model, app.current_controller)

    def finish(self, controller):
        if controller is None:
            return controllers.use('clouds').render()

        app.current_controller = controller
        app.current_model = "conjure-up-{}-{}".format(
            app.env['CONJURE_UP_SPELL'],
            utils.gen_hash())
        async.submit(self.__add_model,
                     self.__handle_exception,
                     queue_name=juju.JUJU_ASYNC_QUEUE)

        c_info = juju.get_controller_info(app.current_controller)
        app.current_cloud = c_info['details']['cloud']
        return controllers.use('deploy').render()

    def render(self):
        existing_controllers = juju.get_controllers()['controllers']
        if len(existing_controllers) == 0:
            return controllers.use('clouds').render()

        metadata = app.config['metadata']
        whitelisted_clouds = [c for c in metadata.get('cloud-whitelist', [])]
        blacklisted_clouds = [c for c in metadata.get('cloud-blacklist', [])]
        if len(whitelisted_clouds) > 0:
            filtered_controllers = {n: d for n, d
                                    in existing_controllers.items()
                                    if d['cloud'] in whitelisted_clouds}
        elif len(blacklisted_clouds) > 0:
            filtered_controllers = {n: d for n, d
                                    in existing_controllers.items()
                                    if d['cloud'] not in blacklisted_clouds}
        else:
            filtered_controllers = existing_controllers

        if len(filtered_controllers) == 0:
            return controllers.use('clouds').render()

        track_screen("Controller Picker")
        excerpt = app.config.get(
            'description',
            "Please select an existing controller,"
            " or choose to bootstrap a new one.")
        view = ControllerListView(app,
                                  filtered_controllers,
                                  self.finish)

        app.ui.set_header(
            title="Choose a Controller or Create new",
            excerpt=excerpt
        )
        app.ui.set_body(view)


_controller_class = ControllerPicker
