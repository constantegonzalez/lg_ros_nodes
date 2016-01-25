#!/usr/bin/env python

"""
lg stats testing scenarios.

starting roslaunch for development:
    roslaunch --screen lg_stats/test/online/test_lg_stats.test
    could do:
    py.test -s -v lg_stats/test/online/test_lg_stats.py

running tests manually:
    rostest lg_stats/test/online/test_lg_stats.test
        (as long as it contains <test> tag, it's the same as launch file)

"""


import os
import unittest
import time
from multiprocessing import Array

import pytest
import rostest
import rospy
import rospkg
import rostopic

from lg_common.helpers import write_log_to_file
from interactivespaces_msgs.msg import GenericMessage
from lg_stats.msg import Stats
from lg_stats import ROS_NODE_NAME
from lg_stats import LG_STATS_DEBUG_TOPIC_DEFAULT


RESULT = Array('c', "UNDEFINED")


class TestLGStats(object):

    def setup_method(self, method):
        RESULT.value = "UNDEFINED"

    @staticmethod
    def callback(msg):
        rospy.loginfo("callback received type: '%s'" % type(msg))
        rospy.loginfo(msg)
        RESULT.value = msg.value

    def test_send_director_scene(self):
        # TODO
        # some stuff will be moved into setup_method / setup_class methods
        # send a scene message which shall result in a reaction on lg_stats/debug topic
        scene_msg = GenericMessage(type="json", message="something")
        pub = rospy.Publisher("/director/scene", GenericMessage, queue_size=3)
        # WARNING: issues retvieving get_param value from the test file, still
        #   getting the default value (regardless of calling it before or after init_node)
        debug_topic = "%s/%s" % (ROS_NODE_NAME,
                                 rospy.get_param("~debug_topic", LG_STATS_DEBUG_TOPIC_DEFAULT))
        rospy.Subscriber(debug_topic, Stats, self.callback)
        rospy.init_node(ROS_NODE_NAME, anonymous=True)
        # after this call the ros infrastructure starts up, sending a message right
        # after this results in a lost message sometimes ... wait
        rospy.sleep(3)
        pub.publish(scene_msg)
        # wait a bit (if it doesn't arrive within 5 seconds, it'll never arrive)
        for count in range(5):
            if RESULT.value != "UNDEFINED":
                break
            rospy.sleep(1)
        assert RESULT.value == "something"


if __name__ == "__main__":
    # pytest must provide result XML file just as rostest.rosrun would do
    # otherwise: FAILURE: test [test_lg_media_basic] did not generate test results
    test_pkg = ROS_NODE_NAME
    test_name = "test_lg_stats"
    test_dir = os.path.join(rospkg.get_test_results_dir(env=None), test_pkg)
    pytest_result_path = os.path.join(test_dir, "rosunit-%s.xml" % test_name)
    # run only itself
    test_path = os.path.abspath(os.path.abspath(__file__))
    # output is unfortunately handled / controlled by above layer of rostest (-s has no effect)
    pytest.main("%s -s -v --junit-xml=%s" % (test_path, pytest_result_path))