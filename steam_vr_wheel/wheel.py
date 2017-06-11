from math import pi, atan2, isclose

import numpy as np
import openvr
from .pyvjoy.vjoydevice import VJoyDevice, HID_USAGE_X, HID_USAGE_RX, HID_USAGE_RY
import time
from collections import deque


FREQUENCY = 60
BUTTONS = {}
BUTTONS['left'] = {openvr.k_EButton_ApplicationMenu: 1, openvr.k_EButton_Grip: 2, openvr.k_EButton_SteamVR_Touchpad: 3,
                   openvr.k_EButton_SteamVR_Trigger: 4
                   }
BUTTONS['right'] = {openvr.k_EButton_ApplicationMenu: 5, openvr.k_EButton_Grip: 6, openvr.k_EButton_SteamVR_Touchpad: 7,
                    openvr.k_EButton_SteamVR_Trigger: 8,
                   }
FULLTURN = 1.5


class Wheel:
    def __init__(self):
        self.device = VJoyDevice(1)
        self.x = 0  # -1 0 1
        self.brake = 0 # 0 1
        self.throttle = 0 # 0 1
        self._wheel_angles = deque(maxlen=10)
        self._wheel_angles.append(0)

    def get_unwrapped(self):
        period = 2 * pi
        angle = np.array(self._wheel_angles)
        diff = np.diff(np.array(angle))
        diff_to_correct = (diff + period / 2.) % period - period / 2.
        increment = np.cumsum(diff_to_correct - diff)
        angle[1:] += increment
        return angle[-1]

    def update(self, left_ctr, right_ctr):
        init = left_ctr.x, left_ctr.y
        a = right_ctr.x, right_ctr.y
        deltaY = a[0] - init[0]
        deltaX = a[1] - init[1]
        angle = (atan2(deltaY, deltaX)+pi/2)
        self._wheel_angles.append(angle)

        wheel_angle = self.get_unwrapped()
        self._wheel_angles[-1] = wheel_angle
        wheel_turn = wheel_angle/(2*pi)
        axisX = int((wheel_turn/FULLTURN+0.5)*0x8000)
        self.device.set_axis(HID_USAGE_X, axisX)
        self.device.set_axis(HID_USAGE_RX, int(left_ctr.axis*0x8000))
        self.device.set_axis(HID_USAGE_RY, int(right_ctr.axis*0x8000))

    def set_button_press(self, button, hand):
        try:
            btn_id = BUTTONS[hand][button]
            self.device.set_button(btn_id, True)
        except KeyError:
            pass

    def set_button_unpress(self, button, hand):
        try:
            btn_id = BUTTONS[hand][button]
            self.device.set_button(btn_id, False)
        except KeyError:
            pass


class Controller:
    def __init__(self, id, name='', vrsys = None):

        self.id = openvr.TrackedDeviceIndex_t(id)

        self.axis = 0
        self.x, self.y, self.z = 0, 0 , 0
        self.name = name
        self.update()

    def update(self, pose=None):
        vrsys = openvr.VRSystem()
        if pose:
            result, pControllerState = vrsys.getControllerState(self.id,
                                                                            openvr.TrackingUniverseSeated
                                                                            )
            self.x = pose.mDeviceToAbsoluteTracking[0][3]
            self.y = pose.mDeviceToAbsoluteTracking[1][3]
            self.z = pose.mDeviceToAbsoluteTracking[2][3]

            self.axis = pControllerState.rAxis[0].x
            self.valid = pose.bPoseIsValid

    def __repr__(self):
        return '<{} {} Controller position x={}, y={}, z={}, axis={} valid={}>'.format(self.name,
                                                                                       self.id,
                                                                                       self.x,
                                                                                       self.y,
                                                                                       self.z,
                                                                                       self.axis,
                                                                                       self.valid)

def do_work(vrsystem, left_controller: Controller, right_controller: Controller, wheel: Wheel, poses):
    vrsystem.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseSeated, 0, len(poses), poses)
    left_controller.update(pose=poses[left_controller.id.value])
    right_controller.update(pose=poses[right_controller.id.value])
    wheel.update(left_controller, right_controller)
    event = openvr.VREvent_t()
    while vrsystem.pollNextEvent(event):
        role = vrsystem.getControllerRoleForTrackedDeviceIndex(event.trackedDeviceIndex)
        hand = None
        if role == openvr.TrackedControllerRole_RightHand:
            hand = 'right'
        if role == openvr.TrackedControllerRole_LeftHand:
            hand = 'left'
        if event.eventType == openvr.VREvent_ButtonPress:
            button = event.data.controller.button
            wheel.set_button_press(button, hand)
        if event.eventType == openvr.VREvent_ButtonUnpress:
            button = event.data.controller.button
            wheel.set_button_unpress(button, hand)



def get_controller_ids(poses):
    vrsys = openvr.VRSystem()
    for i in range(len(poses)):
        device_class = vrsys.getTrackedDeviceClass(i)
        print(device_class)
        if device_class == openvr.TrackedDeviceClass_Controller:
            role = openvr.VRSystem().getControllerRoleForTrackedDeviceIndex(i)
            if role == openvr.TrackedControllerRole_RightHand:
                 right = i
            if role == openvr.TrackedControllerRole_LeftHand:
                 left = i
    return left, right


def main():
    openvr.init(openvr.VRApplication_Background)
    poses_t = openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount
    poses = poses_t()
    vrsystem = openvr.VRSystem()


    hands_got = False
    while not hands_got:
        vrsystem.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseSeated, 0, len(poses), poses)
        try:
            left, right = get_controller_ids(poses)
            hands_got = True
        except NameError:
            pass
        time.sleep(0.1)

    left_controller = Controller(left, name='left', vrsys=vrsystem)
    right_controller = Controller(right, name='right', vrsys=vrsystem)
    wheel = Wheel()
    while True:
        before_work = time.time()
        do_work(vrsystem, left_controller, right_controller, wheel, poses)
        after_work = time.time()
        left = 1/FREQUENCY - (after_work - before_work)
        if left>0:
            time.sleep(left)


if __name__ == '__main__':
    main()