#!/usr/bin/env python

import os
import json
import rospy
import requests

from std_msgs.msg import String
from interactivespaces_msgs.msg import GenericMessage


class AttractLoop:
    def __init__(self, director_scene_publisher, director_presentation_publisher, stop_action, earth_query_publisher, default_presentation=None):
        """
        Class responsible for playing back presentations/scenes that are marked as "attract_loop"
        in Liquid Galaxy content management system.

        """
        self.api_url = rospy.get_param(
            '~director_api_url',
            os.getenv('DIRECTOR_API_URL', 'http://localhost:8034')
        )

        self.earth_query_publisher = earth_query_publisher
        self.stop_action = stop_action
        self.default_presentation = default_presentation
        self.director_scene_publisher = director_scene_publisher
        self.director_presentation_publisher = director_presentation_publisher
        self.attract_loop_queue = []
        self.scene_timer = 0
        self.initialize_timer()

    def initialize_timer(self):
        rospy.Timer(rospy.Duration(1), self._play_attract_loop)

    def _process_activity_state_change(self, message):
        """
        Method responsible for starting (or continuing) of playback for attract loop
        on state change.
        """
        if message.data == True:
            rospy.loginfo("Director: Attract loop becoming inactive")
            self.play_loop = False
            self._stop_attract_loop()
        elif message.data == False:
            self.play_loop = True
        else:
            rospy.logerr("Activity message contained unknown state")

    def _stop_attract_loop(self):
        """
        When state changes to True (active) then we need to decide
        what should be the action that needs to be executed.
        By default earth tour will just stop.
        """
        self.play_loop = False

        rospy.loginfo("Stopping scene timer")

        if self.stop_action == 'stop_playtour':
            stop_tour_msg = String(data='')
            rospy.loginfo("Executing 'stop_playtour' action")
            self.earth_query_publisher.publish(stop_tour_msg)
        elif self.stop_action == 'go_blank':
            pass
        elif self.stop_action == 'load_presentation':
            if self.default_presentation:
                pass
            else:
                rospy.logerr("No default presentation defined")
        else:
            pass

    def _play_attract_loop(self, event):
        """
        Check if there are scenes to continue the attract loop or fetch them and play them back
        """
        rospy.loginfo("Fetching scenes from presentations marked as attract loop")
        try:
            if self.attract_loop_queue:
                rospy.logdebug("attract_loop_queue contains items (%s) continuing from last played scene" % self.attract_loop_queue)
                self._play_attract_loop_item()
            else:
                self.attract_loop_queue = self._fetch_attract_loop_content()['scenes']
                rospy.loginfo("Populated attract_loop_queue with %s" % self.attract_loop_queue)
                self._play_attract_loop_item()
        except Exception, e:
            rospy.logerr("Failed to populate attract loop queue with content because %s" % e)

    def _play_scene(self, scene, presentation, duration):

        rospy.loginfo("Playing scene %s with duration %s" % (scene, duration))

        scene_msg = GenericMessage(type='json', message=scene)
        presentation_msg = GenericMessage(type='json', message=presentation)

        self.director_scene_publisher.publish(scene_msg)
        self.director_presentation_publisher.publish(presentation_msg)

        self.scene_timer = duration

    def _play_attract_loop_item(self):
        rospy.loginfo("Executing _play_attract_loop_item - self.play_loop=%s" % self.play_loop)
        opts = '?format=json'
        rospy.loginfo("Scene timer=%s" % self.scene_timer)

        if self.play_loop and self.scene_timer <= 0:
            scene_presentation = self.attract_loop_queue.pop(0)
            scene = scene_presentation['scene'] # bare object with resource_uri
            scene_url = "%s%s%s" % (self.api_url, scene['resource_uri'], opts)
            presentation = scene_presentation['presentation'] # bare object with resource_uri
            presentation_url = "%s%s%s" % (self.api_url, presentation['resource_uri'], opts)

            full_scene = json.loads(requests.get(scene_url).content) # ROS nodes understandable full scene
            scene_duration = full_scene['duration']
            full_serialized_scene = json.dumps(full_scene)
            serialized_presentation = json.dumps(presentation)

            self._play_scene(full_serialized_scene, serialized_presentation, scene_duration)

        self.scene_timer -= 1

    def _fetch_attract_loop_content(self):
        """
        Fetch presentation groups, presentations and scenes for attract loop.
        Return a dict with the content wherE:
        - presentationgroups is a list of presentationgroups
        - presentations is a list of presentations
        - scenes is alist of dictionaries containing one scene and presentation that it belongs to
            {'scene': <scene>, 'presentation': <presentation>}
        """
        client = requests
        presentationgroups = self._fetch_attract_loop_presentationgroups(client)
        if presentationgroups:
            presentations = self._fetch_presentationgroup_presentations(client, presentationgroups)
            scenes = self._fetch_scenes_from_presentations(client, presentations)
            content =  {'presentationgroups': presentationgroups,
                        'presentations': presentations,
                        'scenes': scenes }
            #rospy.loginfo("Returning content for attract loop: %s" % content)
            return content
        else:
            rospy.loginfo("No presentation groups found in attract loop")
            return

    def _fetch_scenes_from_presentations(self, client, presentations):
        """
        Get all scenes from presentations and fetch the object directly
        so the list is ready to be publised on /director/scene

        Returned list should contain dictionaries like {'scene': <scene>, 'presentation': <presentation>}
        """
        fetched_scenes = []
        for presentation in presentations:
            try:
                presentation_resource_uri = presentation['resource_uri']
                presentation_request = client.get("%s%s" % (self.api_url, presentation_resource_uri)).content
                presentation_scenes = json.loads(presentation_request)['scenes']
            except Exception, e:
                rospy.logerr("Could not fetch presentation scenes from presentations (%s) because %s" % (presentations, e))
                return []

            for scene in presentation_scenes:
                try:
                    #scene_resource_uri = scene['resource_uri']
                    #scene_request = client.get("%s%s" % (DIRECTOR_API_URL, scene_resource_uri)).content
                    #scene = json.loads(scene_request)
                    pass
                except Exception, e:
                    rospy.logerr("Could not fetch scene (%s) from presentation scenes (%s) because %s" % (scene, presentation_scenes, e))
                    return []
                fetched_scenes.extend([{'presentation': presentation, 'scene': scene}])

        #rospy.loginfo("Fetched scenes: %s" % fetched_scenes)
        return fetched_scenes

    def _fetch_presentationgroup_presentations(self, client, presentationgroups):
        """
        """
        attract_loop_presentations = []
        try:
            for presentation in presentationgroups:
                presentation_resource_uri = presentation['resource_uri']
                presentations_request = client.get("%s%s" % (self.api_url, presentation_resource_uri)).content
                presentations = json.loads(presentations_request)['presentations']
                attract_loop_presentations.extend(presentations)
            return attract_loop_presentations
        except Exception, e:
            rospy.logerr("Could not fetch presentations from presentationgroups (%s) because %s" % (presentationgroups, e))
            return []

    def _fetch_attract_loop_presentationgroups(self, client):
        try:
            presentationgroup_request = client.get("%s/director_api/presentationgroup/?attract_loop=True" % self.api_url).content
            presentationgroups = json.loads(presentationgroup_request)['objects']
            assert(type(presentationgroups) == list), "Presentationgroups type is not list"
            return presentationgroups
        except Exception, e:
            rospy.logerr("Could not get presentationgroups because: %s" % e)
            return []

