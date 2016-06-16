import rospy
import threading

from lg_common import ManagedAdhocBrowser
from lg_common.msg import ApplicationState
from lg_common.msg import WindowGeometry
from lg_common.msg import AdhocBrowser, AdhocBrowsers
from lg_common.helpers import get_app_instances_to_manage
from lg_common.helpers import get_app_instances_ids
from lg_common.srv import DirectorPoolQuery


class AdhocBrowserPool():
    """
    Handles browser pool in self.browsers
    Dict(id => ManagedAdhocBrowser)
    """
    def __init__(self, viewport_name):
        """
        AdhocBrowserPool manages a pool of browsers on one viewport.
        self.browsers ivar keeps a dict of (id: ManagedAdhocBrowser) per viewport.
        """
        self.lock = threading.RLock()
        self.viewport_name = viewport_name
        self._init_service()
        self.browsers = {}
        self.log_level = rospy.get_param('/logging/level', 0)

    def process_service_request(self, req):
        """
        Callback for service requests. We always return self.browsers
        """
        rospy.loginfo("POOL %s: Received Query service" % self.viewport_name)
        return str(self.browsers)

    def _init_service(self):
        service = rospy.Service('/browser_service/{}'.format(self.viewport_name),
                                DirectorPoolQuery,
                                self.process_service_request)
        return service

    def _unpack_incoming_browsers(self, browsers):
        """
        Return dict(id: AdhocBrowser) with all AdhocBrowsers with ids as keys
        """
        return {b.id: b for b in browsers}

    def _remove_browser(self, browser_pool_id):
        """
        call .close() on browser object and cleanly delete the object
        """
        rospy.loginfo("POOL %s: Removing browser with id %s" % (self.viewport_name, browser_pool_id))
        with self.lock:
            self.browsers[browser_pool_id].close()
            del self.browsers[browser_pool_id]
            rospy.loginfo("POOL %s: state after %s removal: %s" % (self.viewport_name, browser_pool_id, self.browsers))

    def _create_browser(self, new_browser_pool_id, new_browser):
        """
        Create new browser instance with desired geometry.
        """
        geometry = WindowGeometry(x=new_browser.geometry.x,
                                  y=new_browser.geometry.y,
                                  width=new_browser.geometry.width,
                                  height=new_browser.geometry.height)

        browser_to_create = ManagedAdhocBrowser(geometry=geometry,
                                                log_level=self.log_level,
                                                slug=self.viewport_name + "_" + new_browser_pool_id,
                                                url=new_browser.url)

        browser_to_create.set_state(ApplicationState.VISIBLE)
        rospy.loginfo("POOL %s: Creating new browser %s with id %s" % (self.viewport_name, new_browser, new_browser_pool_id))
        self.browsers[new_browser_pool_id] = browser_to_create
        rospy.loginfo("POOL %s: state after addition of %s: %s" % (self.viewport_name, new_browser_pool_id, self.browsers))
        return True

    def _update_browser(self, browser_pool_id, updated_browser):
        """
        Update existing browser instance
        """
        rospy.loginfo("POOL %s: state during updating: %s" % (self.viewport_name, self.browsers))
        current_browser = self.browsers[browser_pool_id]
        rospy.loginfo("Updating browser %s to it's new state: %s" % (current_browser, updated_browser))
        future_url = updated_browser.url
        future_geometry = WindowGeometry(x=updated_browser.geometry.x,
                                         y=updated_browser.geometry.y,
                                         width=updated_browser.geometry.width,
                                         height=updated_browser.geometry.height)

        current_geometry = current_browser.geometry

        if current_browser.url != future_url:
            with self.lock:
                self._update_browser_url(browser_pool_id, current_browser, future_url)
        else:
            rospy.loginfo("POOL %s: not updating url of browser %s (old url=%s, new url=%s)" %
                          (self.viewport_name, current_browser, current_browser.url, future_url))

        with self.lock:
            geom_success = self._update_browser_geometry(browser_pool_id, current_browser, future_geometry)
            if geom_success:
                rospy.loginfo("Successfully updated browser(%s) geometry from %s to %s" % (browser_pool_id, current_geometry, future_geometry))
            else:
                rospy.logerr("Could not update geometry of browser (%s) (from %s to %s)" % (browser_pool_id, current_geometry, future_geometry))

    def _update_browser_url(self, browser_pool_id, current_browser, future_url):
        try:
            rospy.loginfo("Updating URL of browser id %s from %s to %s" % (browser_pool_id, current_browser.url, future_url))
            current_browser.update_url(future_url)
            return True
        except Exception, e:
            rospy.logerr("Could not update url of browser id %s because: %s" % (browser_pool_id, e))
            return False

    def _update_browser_geometry(self, browser_pool_id, current_browser, future_geometry):
        try:
            current_browser.update_geometry(future_geometry)
            rospy.loginfo("Updated geometry of browser id %s" % browser_pool_id)
            return True
        except Exception, e:
            rospy.logerr("Could not update geometry of browser id %s because: %s" % (browser_pool_id, e))
            return False

    def handle_ros_message(self, data):
        """
        - if message has no AdhocBrowser messages in the array,
        shutdown all browsers
        - if the message has AdhocBrowser messages in the array:
        -- check for an existing browser with the same id.
        --- if it exists, update the url and geometry.
        --- if no existing browser, create one.
        --- if an existing browser has an id that doesn't match the new message, then
            shut it down and remove it from the tracked instances.

        Arguments:
            data: AdhocBrowsers, which is an array of AdhocBrowser

        """

        incoming_browsers = self._unpack_incoming_browsers(data.browsers)
        incoming_browsers_ids = set(incoming_browsers.keys())  # set
        current_browsers_ids = get_app_instances_ids(self.browsers)  # set

        # remove
        browsers_to_remove = get_app_instances_to_manage(current_browsers_ids,
                                                         incoming_browsers_ids,
                                                         manage_action='remove')

        rospy.loginfo("POOL %s: browsers to remove = %s" % (self.viewport_name, browsers_to_remove))
        for browser_pool_id in browsers_to_remove:
            rospy.loginfo("Removing browser id %s" % browser_pool_id)
            self._remove_browser(browser_pool_id)

        # create
        browsers_to_create = get_app_instances_to_manage(current_browsers_ids,
                                                         incoming_browsers_ids,
                                                         manage_action='create')

        rospy.loginfo("POOL %s: browsers to create = %s" % (self.viewport_name, browsers_to_create))
        for browser_pool_id in browsers_to_create:
            rospy.loginfo("Creating browser with id %s" % browser_pool_id)
            self._create_browser(browser_pool_id, incoming_browsers[browser_pool_id])

        # update
        browsers_to_update = get_app_instances_to_manage(current_browsers_ids,
                                                         incoming_browsers_ids,
                                                         manage_action='update')

        rospy.loginfo("POOL %s: browsers to update = %s" % (self.viewport_name, browsers_to_update))
        for browser_pool_id in browsers_to_update:
            rospy.loginfo("Updating browser with id %s" % browser_pool_id)
            self._update_browser(browser_pool_id, incoming_browsers[browser_pool_id])

        return True

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
