#!/usr/bin/env python
from __future__ import division

import numpy as np
import math
import tf
from tf import transformations as tf_trans
import rospy
## Possibly necessary:
# import time
# import threading

## Ros msgs
from std_msgs.msg import Header
from geometry_msgs.msg import Pose, PoseStamped, Twist, TwistStamped, Vector3

# Try a Forrest style locking function

max_linear_vel = 1
max_linear_acc = max_linear_vel

max_angular_vel = 2
max_angular_acc = max_angular_vel

def xyzw_array(quaternion):
    xyzw_array = np.array([quaternion.x, quaternion.y, quaternion.z, quaternion.w])
    return(xyzw_array)


def print_in(f):
    def print_on_entry(*args, **kwargs):
        print("Executing " + f.func_name)
        return( f(*args, **kwargs) )
    return(print_on_entry)


class Controller(object):
    '''Controller object 
    See Jacob Panikulam or Aaron Marquez for questions
    
    Special glory to Lord Forrest Voight, creator of the universe
    Greater thanks to the incredible, brilliant and good-looking Khaled Hassan, for his unyielding mentorship
    and love for Burrito Bros
    '''
    def __init__(self):
        '''Initialize Controller Object'''
        rospy.init_node('controller')

        # Twist pub
        twist_topic = 'navigation_control_signals'
        self.twist_pub = rospy.Publisher(twist_topic, Twist) 
        
        # Current pose sub
        self.pose_sub = rospy.Subscriber('pose', PoseStamped, self.got_pose)
        self.desired_pose_sub = rospy.Subscriber('desired_pose', Twist, self.got_desired_pose)
        
        # Initializations to avoid weird things
        self.des_position = np.array([100, 100])
        self.des_yaw = np.pi*3.0/2.0

        self.position = None
        self.yaw = None

    def send_twist(self, (xvel,yvel), angvel):
        '''send_twist((xvel,yvel), angvel)
        Generate twist message
        '''
        self.twist_pub.publish(
            Twist(
                linear=Vector3(xvel, yvel, 0),
                angular=Vector3(0, 0, angvel),
            )
        )

    def norm_angle_diff(self, ang_1, ang_2):
        '''norm_angle_diff(ang_1, ang_2)
        -> Normalized angle difference, constrained to [-pi, pi]
        '''
        return (ang_1 - ang_2 + math.pi) % (2 * math.pi) - math.pi

    def unit_vec(self, v):
        '''unit_vec(v)
        '''
        norm = np.linalg.norm(v)
        if norm == 0:
            return(v)
        return np.array(v)/np.linalg.norm(v)

    def sign(self, x):
        if x > 0: return 1
        elif x < 0: return -1
        else: return 0

    def got_pose(self, msg):
        self.position = np.array([msg.pose.position.x, msg.pose.position.y])
        self.yaw = tf_trans.euler_from_quaternion(xyzw_array(msg.pose.orientation))[2]
        print tf_trans.euler_from_quaternion(xyzw_array(msg.pose.orientation))
        # if((self.position is None) or (self.yaw is None)):
            ## Ain't doin shit if we don't know where we at!
            # return

        position_error = self.des_position - self.position
        yaw_error = self.norm_angle_diff(self.des_yaw, self.yaw)
        print 'Yaw error:',yaw_error
        linear_speed = min(
                         math.sqrt(2 * np.linalg.norm(position_error) * max_linear_acc),
                         max_linear_vel
                        )
        angular_speed = min(
                         math.sqrt(2 * abs(yaw_error) * max_angular_acc), 
                         max_angular_vel
                        )

        desired_vel = linear_speed * self.unit_vec(position_error)
        desired_angvel = angular_speed * self.sign(yaw_error)

        forward = np.array([math.cos(self.yaw), math.sin(self.yaw)])
        left = np.array([math.cos(self.yaw + math.pi/2), math.sin(self.yaw + math.pi/2)])

        self.send_twist(
            (
                forward.dot(desired_vel), 
                left.dot(desired_vel)
            ), 
            desired_angvel
        )

    def got_desired_pose(self, msg):
        '''Figure out how to do this in a separate thread
         So we're not depending on a message to act
        #LearnToThreading
        (That's a hashtag)
        '''
        self.des_position = np.array([msg.pose.position.x, msg.pose.position.y])
        self.des_yaw = tf_trans.euler_from_quaternion(xyzw_array(msg.pose.orientation))[2]



controller = Controller()
rospy.spin()