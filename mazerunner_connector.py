import phantom.app as phantom

from phantom.base_connector import BaseConnector
from phantom.action_result import ActionResult
from requests import ConnectionError
import os

app_dir = os.path.dirname(os.path.abspath(__file__))
os.sys.path.insert(0, '{}/dependencies'.format(app_dir))  # noqa

# Imports local to this App
from mazerunner_consts import MAZERUNNER_SERVER, \
    MAZERUNNER_KEY_ID, \
    MAZERUNNER_SECRET, \
    MAZERUNNER_CRT_FILE  # noqa

# import simplejson as json
import datetime  # noqa
import tempfile  # noqa
import zipfile  # noqa
import os  # noqa
import time  # noqa
import uuid  # noqa

import mazerunner  # noqa


def _json_fallback(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    else:
        return obj


# Define the App Class
class CymmetriaMazeRunnerConnector(BaseConnector):
    PHANTOM_DEPLOY_GROUP_NAME = 'Phantom Deploy Group'
    PHANTOM_BREADCRUMB_NAME = 'Phantom SMB Breadcrumb'
    PHANTOM_SERVICE_NAME = 'Phantom SMB Service'
    PHANTOM_DECOY_NAME = 'Phantom Backup Server'
    ACTION_ID_CREATE_BREADCRUMB_MSI = 'create_breadcrumb_file'

    def __init__(self):
        # Call the BaseConnectors init first
        super(CymmetriaMazeRunnerConnector, self).__init__()

        # client member for the mazerunner client
        self.client = None

    def _init_mazeclient(self):
        """
        Init the connection to the MazeRunner Platform

        :return:
        """
        if self.client:
            return

        config = self.get_config()
        if config:
            self.client = mazerunner.connect(
                ip_address=config.get(MAZERUNNER_SERVER),
                api_key=config.get(MAZERUNNER_KEY_ID),
                api_secret=config.get(MAZERUNNER_SECRET),
                certificate=config.get(MAZERUNNER_CRT_FILE)
            )

    def _test_connectivity(self):
        self.save_progress('Trying to connect to MazeRunner...')

        try:
            self._init_mazeclient()
        except ConnectionError:
            return self.get_status()

        return self.set_status_save_progress(
            phantom.APP_SUCCESS,
            "MazeRunner Connection Test passed")

    def __create_temp_file(self):
        """
        this function creates an empty temporary file and returns a path to the file
        """
        temp_file = tempfile.mkstemp()
        os.close(temp_file[0])
        return temp_file[1]

    def __create_dummy_zip_file(self):
        """
        This function creates a dummy zip file and returns a path to the file
        """
        text_file_path = self.__create_temp_file()
        zip_file_path = self.__create_temp_file()

        with zipfile.ZipFile(zip_file_path, "w") as zip_file:
            zip_file.write(text_file_path)

            os.remove(text_file_path)

        return zip_file_path

    def __add_decoy(self):
        decoy = self.client.decoys.create(name=self.PHANTOM_DECOY_NAME,
                                          hostname="nas-backup-02",
                                          os="Ubuntu_1404",
                                          vm_type="KVM")
        while decoy.machine_status != "not_seen":  # make sure the decoy was created
            time.sleep(5)
            decoy.load()

        return decoy

    def __add_smb_service(self, decoy):
        # Create a service
        # Different services allow you to mimic different resources you have on your network
        smb_zip_file = self.__create_dummy_zip_file()
        service = self.client.services.create(name=self.PHANTOM_SERVICE_NAME, service_type="smb", share_name="accounting",
                                         zip_file_path=smb_zip_file)
        os.remove(smb_zip_file)

        # Connect the service to the decoy
        # When a service is connected to a decoy, you may access the service on the decoy.
        # Any such interaction will generate an alert
        service.connect_to_decoy(decoy.id)

        return service

    def __add_breadcrumbs(self, service):
        username = 'user123'
        password = 'pass123'

        # Create breadcrumb
        # Breadcrumbs can be deployed on endpoints
        # to trick an attacker to interact with a decoy and generate an alert
        breadcrumb = self.client.breadcrumbs.create(
            name=self.PHANTOM_BREADCRUMB_NAME,
            breadcrumb_type="netshare",
            username=username,
            password=password)

        # Connect the breadcrumb to the service
        # When a breadcrumb is connected to a service, the credential and other information
        # found in the breadcrumb will be usable with the service
        breadcrumb.connect_to_service(service.id)

        return breadcrumb

    def __get_deployment_group_deployment_file(self, deployment_group, msi_file_name):
        full_path = '/tmp/{}'.format(msi_file_name)

        deployment_group.deploy(full_path, 'Windows', 'install', 'MSI')
        return '{}.msi'.format(msi_file_name)

    def _add_decoy_complete(self, msi_file_name):

        # Add  new decoy
        decoy = self.__add_decoy()

        # Add the SMB service
        service = self.__add_smb_service(decoy)

        # Add breadcrumbs to our service
        breadcrumb = self.__add_breadcrumbs(service)

        # Create the deployment_group and add the breadcrumb to it:
        dp_group = self.client.deployment_groups.create(self.PHANTOM_DEPLOY_GROUP_NAME)
        breadcrumb.add_to_group(dp_group.id)

        # Turn on the decoy
        # After we set up the entire deception chain - its time to power on the decoy!
        decoy.power_on()

        while decoy.machine_status != 'active':  # make sure the decoy is active
            print(decoy.machine_status)
            time.sleep(5)
            decoy.load()

        return self.__get_deployment_group_deployment_file(dp_group, msi_file_name)

    def _get_deployment_group_full_check(self):
        """
        Return the Deployment Group if exists and everything is ok (breadcrumb connected to service which also connected to a decoy (and the decoy is active))

        :param bc_name:
        :return: mazerunner.Breadcrumb
        """

        # Find all deployment groups by the Phantom's specific deployment group
        dps = [x for x in self.client.deployment_groups if x.name == self.PHANTOM_DEPLOY_GROUP_NAME]
        if not dps:
            return
        dp = dps[0]

        if dp.is_active:
            return dp

        bcs = [x for x in self.client.breadcrumbs if x.name == self.PHANTOM_BREADCRUMB_NAME and self.PHANTOM_DEPLOY_GROUP_NAME in [y.name for y in x.deployment_groups]]
        if not bcs:
            return
        bc = bcs[0]

        # We use this because ver1.0 has a bug with the attached_services.
        # The data returned is instance of Decoy instead of Service
        services = [self.client.services.get_item(x.id) for x in bc.attached_services if x.name == self.PHANTOM_SERVICE_NAME]

        if not services:
            return
        srv = services[0]

        decoys = [x for x in srv.attached_decoys if x.name == self.PHANTOM_DECOY_NAME]
        if not decoys:
            return
        dec = decoys[0]

        # Turn on the decoy
        # After we set up the entire deception chain - its time to power on the decoy!
        dec.power_on()

        while dec.machine_status != 'active':  # make sure the decoy is active
            print(dec.machine_status)
            time.sleep(5)
            dec.load()

        return dp

    def _create_decoy(self, param):
        self._init_mazeclient()

        msi_file_name = "{}".format(uuid.uuid4())
        dp_group = self._get_deployment_group_full_check()
        self.debug_print("param")
        self.debug_print("dp_group", dp_group)

        action_result = ActionResult(dict(param))
        action_result.add_data({'msi_file': msi_file_name})
        self.add_action_result(action_result)

        self.debug_print("action_result", action_result)

        if dp_group:
            self.__get_deployment_group_deployment_file(dp_group, msi_file_name)
            action_result.set_status(phantom.APP_SUCCESS)
        else:
            self._add_decoy_complete(msi_file_name)
            action_result.set_status(phantom.APP_SUCCESS)

        return action_result.get_status()

    def handle_action(self, param):

        ret_val = phantom.APP_SUCCESS

        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()

        self.debug_print("action_id", self.get_action_identifier())

        if action_id == phantom.ACTION_ID_TEST_ASSET_CONNECTIVITY:
            ret_val = self._test_connectivity()
        elif action_id == self.ACTION_ID_CREATE_BREADCRUMB_MSI:
            ret_val = self._create_decoy(param)

        return ret_val


if __name__ == '__main__':
    # Nothing here currently
    pass
