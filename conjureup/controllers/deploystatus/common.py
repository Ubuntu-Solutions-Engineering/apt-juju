import asyncio

from conjureup import events, utils
from conjureup.app_config import app


async def wait_for_applications(msg_cb):
    await events.DeploymentComplete.wait()
    msg = 'Waiting for deployment to settle.'
    app.log.info(msg)
    msg_cb(msg)

    # retry done check a few times to work around
    # https://bugs.launchpad.net/juju-wait/+bug/1680963
    for i in range(3):
        try:
            await utils.run_step('00_deploy-done',
                                 'deployment watcher',
                                 msg_cb)
            break
        except Exception as e:
            if i < 2 and 'Applications did not start successfully' in str(e):
                await asyncio.sleep(5)
                app.log.debug('Retrying 00_deploy-done: {}'.format(i))
                continue
            raise

    events.ModelSettled.set()
    msg = 'Model settled.'
    app.log.info(msg)
    msg_cb(msg)
