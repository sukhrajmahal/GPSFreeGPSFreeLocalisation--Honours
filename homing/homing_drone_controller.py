# Script Related Imports
import logging
from random import randint
from enum import Enum

# Crazyflie Realted Imports
import time
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.motion_commander import MotionCommander

# Bluetooth Related Imports
import asyncio
from bleak import discover

class Direction(Enum):
    NORTH = 1
    NORTH_EAST = 2
    EAST = 3
    SOUTH_EAST = 4
    SOUTH = 5
    SOUTH_WEST = 6
    WEST = 7
    NORTH_WEST = 8
    LAND = 9
    NONE = 0


# This Class is very similar to the INS Folder's Drone Controller,
# Especially in the set up and use of the crazyflie. However, a different 
# class made as DroneController has more logging requirements. Also
# adding the homing implementation would make it too long.
# An alternative would be to put shared code in a new class. But it would 
# not be worth it. Considerting this only a aid script.
class HomingDroneController:
    # Drone related variables
    URI = 'radio://0/80/250K'
    DRONE_BLUETOOTH_ADDRESS = 'EF4F8CDB-A789-4854-A85E-1A9567EEABBE'
    NUM_SAMPLES_OF_RSSI = 10

    ### Crazyflie Set up and communication methods ###

    def __init__(self):
        # Initialize the low-level drivers (don't list the debug drivers)
        cflib.crtp.init_drivers(enable_debug_driver=False)
        logging.info('Controller: Low level Crazyflie drivers are set up')
        self.is_connected = False

    def connect_to_crazyflie(self):
        available_drones = cflib.crtp.scan_interfaces()

        # Checking that we found the drone
        if len(available_drones) == 0:
            logging.error("Controller: Connect to crazyflie method could not find crazyflie")
            raise Exception("Crazyflie cannot be found")

        for drone in available_drones:
            logging.debug("Controller: Found the following Drones: " + drone[0])

        # Creating a new crazyflie default object
        crazyflie = Crazyflie(rw_cache='./cache')

        # Setting up callbacks telling Crazyflie what to do
        crazyflie.disconnected.add_callback(self.drone_disconnected)
        crazyflie.connection_failed.add_callback(self.drone_connection_failed)
        crazyflie.connection_lost.add_callback(self.drone_connection_lost)

        logging.debug("Controller: Connecting to %s", HomingDroneController.URI)
        # Connecting to the crazyflie
        crazyflie.open_link(HomingDroneController.URI)
        # Variable to keep the python script running while connected
        self.is_connected = True

        return crazyflie



    ### Bluetooth Related Methods ###

    def get_drone_rssi(self):
        # Private method to get the Bluetooth RSSI of the drone
        async def get_rssi():
            devices = await discover(1)
            for d in devices:
                if d.address == HomingDroneController.DRONE_BLUETOOTH_ADDRESS:
                    return d.rssi

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(get_rssi())

    def get_average_rssi(self, num_samples=10): 
        sum = 0
        average_rssi = 0

        for x in range(num_samples):
            rssi = self.get_drone_rssi()
            sum += abs(rssi)

        if sum != 0:
            average_rssi = sum / num_samples
        return average_rssi

    
    ### Nine Point Sampling Methods ###
    
    def nine_point_sample(self, motion_commander, jump_distance, num_samples):
        # Method will test 9 different spots and test which provides the strongest
        # Connection. It will then return the direction which is best suited

        nine_point_sample = [[0, 0, 0],
                             [0, 0, 0],
                             [0, 0, 0]]

        best_singal_strength = 0
        best_direction = Direction.NONE

        # The calling method has already taken care of taking off. 
        # Therefore we get the first sample without moving
        current_position = self.get_average_rssi(num_samples)

        # Now we move to forward
        motion_commander.forward(jump_distance)
        time.sleep(1)
        # We assign thi one to the best RSSI as it is the first one
        # We compare the current position one later
        best_singal_strength = self.get_average_rssi(10)
        best_singal_direction = Direction.NORTH

        # Checking one forward and one right of origin
        motion_commander.right(jump_distance)
        rssi = self.get_average_rssi(num_samples)
        # Checking if it is better than the previous one
        if rssi < best_singal_strength:
            best_singal_strength = rssi
            best_singal_direction = Direction.NORTH_EAST

        # Checking to right of origin
        motion_commander.back(jump_distance)
        rssi = self.get_average_rssi(num_samples)
        # Checking if it is better than the previous one
        if rssi < best_singal_strength:
            best_singal_strength = rssi
            best_singal_direction = Direction.EAST

        # Checking one right, one back of origin
        motion_commander.back(jump_distance)
        rssi = self.get_average_rssi(num_samples)
        # Checking if it is better than the previous one
        if rssi < best_singal_strength:
            best_singal_strength = rssi
            best_singal_direction = Direction.SOUTH_EAST

        # Checking one back from origin
        motion_commander.left(jump_distance)
        rssi = self.get_average_rssi(num_samples)
        # Checking if it is better than the previous one
        if rssi < best_singal_strength:
            best_singal_strength = rssi
            best_singal_direction = Direction.SOUTH

        # Checking one left and one back from origin
        motion_commander.left(jump_distance)
        rssi = self.get_average_rssi(num_samples)
        # Checking if it is better than the previous one
        if rssi < best_singal_strength:
            best_singal_strength = rssi
            best_singal_direction = Direction.SOUTH_WEST

        # Checking left
        motion_commander.forward(jump_distance)
        rssi = self.get_average_rssi(num_samples)
        # Checking if it is better than the previous one
        if rssi < best_singal_strength:
            best_singal_strength = rssi
            best_singal_direction = Direction.WEST

        # Checking one left and one forward
        motion_commander.forward(jump_distance)
        rssi = self.get_average_rssi(num_samples)
        # Checking if it is better than the previous one
        if rssi < best_singal_strength:
            best_singal_strength = rssi
            best_singal_direction = Direction.NORTH_WEST

        # Checking which direction is the best
        if best_singal_strength < current_position:
            return best_singal_direction
        else:
            return Direction.NONE

    
    def fly_direction(self, motion_commander, direction, jump_distance):
        # Apparently python doesnt have a case switch. 
        # Maybe a dictionary storing directions with their motion commander forward etc would be cleaner
        # However, some directions need to make 2 moves
        if direction == Direction.NORTH:
            motion_commander.forward(jump_distance)
        elif direction == Direction.NORTH_EAST:
            # Motion commander has methods to move diagonally but in my experience it behaves oddly
            motion_commander.forward(jump_distance)
            motion_commander.right(jump_distance)
        elif direction == Direction.EAST:
            motion_commander.right(jump_distance)
        elif direction == Direction.SOUTH_EAST:
            motion_commander.back(jump_distance)
            motion_commander.right(jump_distance)
        elif direction == Direction.SOUTH:
            motion_commander.back(jump_distance)
        elif direction == Direction.SOUTH_WEST:
            motion_commander.back(jump_distance)
            motion_commander.left(jump_distance)
        elif direction == Direction.WEST:
            motion_commander.left(jump_distance)
        elif direction == Direction.NORTH_WEST:
            motion_commander.forward(jump_distance)
            motion_commander.left(jump_distance)

    ### Homing Methdos ###

    def basic_homing(self):
        logging.debug('Starting Basic Homing')
        # Connecting to the crazyflie
        crazyflie = self.connect_to_crazyflie()

        # We take off when the commander is created
        with MotionCommander(crazyflie) as mc:
            # Tracking Variables
            jump_distance = 0.5
            previous_direction = Direction.NONE
            num_moves = 0
            num_nine_point_samples = 0
            rssi_landing_threshold = 30
            
            while num_moves < 20:
                # Check if we can land
                current_rssi = self.get_average_rssi(self.NUM_SAMPLES_OF_RSSI)
                if current_rssi <= rssi_landing_threshold:
                    # We have made it to the beacon and should land
                    # We simply break out of loop as crazyflie will land when
                    # the program breaks out of the motion comanders scope
                    break

                # Try to move in the same direction that we moved in previously
                # However if we moved in no direction (start and when we random) we need to sample
                if previous_direction == Direction.NONE:
                    best_direction = self.nine_point_sample(mc, jump_distance, self.NUM_SAMPLES_OF_RSSI)
                    num_nine_point_samples += 1

                    # If the best direction is none, we make one jump in a random direction
                    # However, we leave the previous direction none so that we trigger the 
                    # sampling again
                    if best_direction == Direction.NONE:
                        # Finding the random direction to move in
                        random_direction = Direction(randint(1,8)).name
                        self.fly_direction(mc, random_direction, jump_distance)
                        num_moves += 1
                    else:
                        # Flying in the best direction
                        self.fly_direction(mc, best_direction, jump_distance)
                        # Updating best direction
                        previous_direction = best_direction
                        num_moves += 1
                else:
                    # We have a previous direction we will move again in this direction
                    self.fly_direction(mc, previous_direction, jump_distance)
                    # Getting RSSI and checking if it gets better
                    new_rssi = self.get_average_rssi()
                    if new_rssi > current_rssi:
                        # We have gotten to a worse position
                        # Finding the reverse of the direction we moved in
                        reverse_direction = Direction((previous_direction.value + 4) % 8)
                        self.fly_direction(mc, reverse_direction, jump_distance)
                        # Set the previous direction to none, so that we resample
                        previous_direction = Direction.NONE
                    else:
                        # We have moved to the right spot.
                        num_moves += 1

            # Printing out the stats 
            print("Basic Homing: Num Nine Point Samples: " + str(num_nine_point_samples))
            print("Basic Homing: Num Moves: " + str(num_moves))

        while self.is_connected:
            time.sleep(1)
            
    def ranged_homing(self):
        logging.debug('Starting Ranged Homing')
        # Connecting to the crazyflie
        crazyflie = self.connect_to_crazyflie()

        # We take off when the commander is created
        with MotionCommander(crazyflie) as mc:
            # Tracking Variables
            previous_direction = Direction.NONE
            num_moves = 0
            num_nine_point_samples = 0
            rssi_landing_threshold = 30
            
            while num_moves < 20:
                # Check if we can land
                current_rssi = self.get_average_rssi(self.NUM_SAMPLES_OF_RSSI)
                if current_rssi <= rssi_landing_threshold:
                    # We have made it close to the beacon.
                    # We should try move closer to the beacon in much smaller steps
                    while(previous_direction != Direction.NONE):
                        self.fly_direction(mc, previous_direction, 0.1)
                        temp_rssi = self.get_average_rssi()
                        # Checking if the RSSI value improved
                        if temp_rssi < current_rssi:
                            num_moves += 1
                        else:
                            # Flying back
                            reverse_direction = Direction((previous_direction.value + 4) % 8)
                            self.fly_direction(mc, reverse_direction, 0.1)
                            # Breaking out of this loop which will break out the next loop and let
                            # the drone land (Good coding is my passion)
                            break
                    break

                # Getting the jump distance based on which zone we are in
                jump_distance = 0.5
                if current_rssi > 55:
                    jump_distance = 1.5

                # Try to move in the same direction that we moved in previously
                # However if we moved in no direction (start and when we random) we need to sample
                if previous_direction == Direction.NONE:
                    best_direction = self.nine_point_sample(mc, jump_distance, self.NUM_SAMPLES_OF_RSSI)
                    num_nine_point_samples += 1

                    # If the best direction is none, we make one jump in a random direction
                    # However, we leave the previous direction none so that we trigger the 
                    # sampling again
                    if best_direction == Direction.NONE:
                        # Finding the random direction to move in
                        random_direction = Direction(randint(1,8)).name
                        self.fly_direction(mc, random_direction, jump_distance)
                        num_moves += 1
                    else:
                        # Flying in the best direction
                        self.fly_direction(mc, best_direction, jump_distance)
                        # Updating best direction
                        previous_direction = best_direction
                        num_moves += 1
                else:
                    # We have a previous direction we will move again in this direction
                    self.fly_direction(mc, previous_direction, jump_distance)
                    # Getting RSSI and checking if it gets better
                    new_rssi = self.get_average_rssi()
                    if new_rssi > current_rssi:
                        # We have gotten to a worse position
                        # Finding the reverse of the direction we moved in
                        reverse_direction = Direction((previous_direction.value + 4) % 8)
                        self.fly_direction(mc, reverse_direction, jump_distance)
                        # Set the previous direction to none, so that we resample
                        previous_direction = Direction.NONE
                    else:
                        # We have moved to the right spot.
                        num_moves += 1

            # Printing out the stats 
            print("Basic Homing: Num Nine Point Samples: " + str(num_nine_point_samples))
            print("Basic Homing: Num Moves: " + str(num_moves))

        while self.is_connected:
            time.sleep(1)



    ### Crazyflie Connection Related Callbacks ###

    def drone_disconnected(self, link_uri):
        logging.info('Controller: Disconnected from %s' % link_uri)
        self.is_connected = False

    def drone_connection_failed(self, link_uri, msg):
        logging.error('Controller: Connection to %s failed: %s' % (link_uri, msg))
        self.is_connected = False

    @staticmethod
    def drone_connection_lost(self, link_uri, msg):
        logging.warning('Controller: Connection to %s lost: %s' % (link_uri, msg))
        self.is_connected = False
