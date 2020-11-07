import logging
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.motion_commander import MotionCommander

from logcreater import LogCreater

class DroneController:
    # Drone related variables
    URI = 'radio://0/80/250K'
    state_estimate_x = 0
    state_estimate_y = 0
    # Logging variables
    accel_logger = LogCreater.setup_logger("AccelLogger")
    state_logger = LogCreater.setup_logger("StateEstimate")



    ### Crazyflie Set up and communication methods ###

    def __init__(self):
        # Initialize the low-level drivers (don't list the debug drivers)
        cflib.crtp.init_drivers(enable_debug_driver=False)
        logging.info('DroneController: Low level Crazyflie drivers are set up')
        self.is_connected = False
        self.logConfigs = []

    def connect_to_crazyflie(self):
        available_drones = cflib.crtp.scan_interfaces()

        # Checking that we found the drone
        if len(available_drones) == 0:
            logging.error("DroneController: Connect to crazyflie method could not find crazyflie")
            raise Exception("Crazyflie cannot be found")

        for drone in available_drones:
            logging.debug("DroneController: Found the following Drones: " + drone[0])

        # Creating a new crazyflie default object
        crazyflie = Crazyflie(rw_cache='./cache')

        # Setting up callbacks telling Crazyflie what to do
        crazyflie.disconnected.add_callback(self.drone_disconnected)
        crazyflie.connection_failed.add_callback(self.drone_connection_failed)
        crazyflie.connection_lost.add_callback(self.drone_connection_lost)

        logging.debug("DroneController: Connecting to %s" % DroneController.URI)
        # Connecting to the crazyflie
        crazyflie.open_link(DroneController.URI)
        # Variable to keep the python script running while connected
        self.is_connected = True

        return crazyflie



    ### Crazyflie Logging Setup Related Methods ###
    
    def setup_logging(self, crazyflie, results_folder):
        # Setting the accelerometer logging
        self.setup_accel_logging(crazyflie, results_folder)
        self.setup_state_logging(crazyflie, results_folder)

        # Starting all the log configs that we have added
        for config in self.logConfigs:
            try:
                config.start()
            except KeyError as e:
                logging.error('Could not start log configuration,'
                              '{} not found in TOC'.format(str(e)))

    def setup_accel_logging(self, crazyflie, results_folder):
        # Creating the logging file for the accelerometer
        result_file = results_folder + "AccelLog.txt"
        # Setting up the logger to use this file. Yes this set up is not ideal. But the file name depends on
        # The Algroithm name, x and y distance, and the number of samples. Therefore must be set on the fly
        DroneController.clear_handlers(DroneController.accel_logger)
        accel_log_handler = logging.FileHandler(result_file)
        DroneController.accel_logger.addHandler(accel_log_handler)

        accel_config = LogConfig(name='Accelerometer', period_in_ms=10)
        accel_config.add_variable('acc.x', 'float')
        accel_config.add_variable('acc.y', 'float')
        accel_config.add_variable('acc.z', 'float')

        # Adding the configuration cannot be done until a Crazyflie is connected, since we need to
        # check that the variables we would like to newLog are in the TOC.
        try:
            # Adding the log config to the crazyflie
            crazyflie.log.add_config(accel_config)

            # Setting up the call back methods
            # Callback for error logging
            accel_config.error_cb.add_callback(self.log_error)
            # Callback for normal data recording
            accel_config.data_received_cb.add_callback(self.log_accel_data)
            # Adding to the log configs so that we can start in the setup_logging method
            self.logConfigs.append(accel_config)
        except AttributeError:
            logging.error('Could not add Accelerometer log config, bad configuration.')

    def setup_state_logging(self, crazyflie, results_folder):
        # Creating the logging file for the state esitmation
        result_file = results_folder + "StateLog.txt"
        # Setting up the logger to use this file. Yes this set up is not ideal as discussed in accel logging
        # set up. 
        DroneController.clear_handlers(DroneController.state_logger)
        state_log_handler = logging.FileHandler(result_file)
        DroneController.state_logger.addHandler(state_log_handler)

        state_config = LogConfig(name='StateEstimate', period_in_ms=10)
        state_config.add_variable('stateEstimate.x', 'float')
        state_config.add_variable('stateEstimate.y', 'float')
        state_config.add_variable('stateEstimate.z', 'float')

        try:
            crazyflie.log.add_config(state_config)
            state_config.error_cb.add_callback(self.log_error)
            state_config.data_received_cb.add_callback(self.log_state_data)
            self.logConfigs.append(state_config)
        except AttributeError:
            logging.error('Could not add Accelerometer log config, bad configuration.')

    @staticmethod
    def clear_handlers(logger):
        handlers = logger.handlers
        for handler in handlers:
            logger.removeHandler(handler)



    ### Sensor Logging Related Callbacks ###

    @staticmethod
    def log_error(self, logconf, msg):
        """Callback from the log API when an error occurs"""
        logging.error('Drone Controller: Error when logging %s: %s' % (logconf.name, msg))

    @staticmethod
    def log_accel_data(self, timestamp, data, logconf):
        DroneController.accel_logger.info('ACCEL [%d][%s]: %s' % (timestamp, logconf.name, data))

    @staticmethod
    def log_state_data(self, timestamp, data, logconf):
        DroneController.state_logger.info('STATE [%d][%s]: %s' % (timestamp, logconf.name, data))
        # Keeping track of the latest position
        if logconf.name == 'stateEstimate.x':
            DroneController.state_estimate_x = float(data)
        if logconf.name == 'stateEstimate.y':
            DroneController.state_estimate_y = float(data)


    ### Crazyflie Connection Related Callbacks ###

    def drone_disconnected(self, link_uri):
        logging.info('DroneController: Disconnected from %s' % link_uri)
        self.is_connected = False

    def drone_connection_failed(self, link_uri, msg):
        logging.error('DroneController: Connection to %s failed: %s' % (link_uri, msg))
        self.is_connected = False

    @staticmethod
    def drone_connection_lost(self, link_uri, msg):
        logging.warning('DroneController: Connection to %s lost: %s' % (link_uri, msg))
        self.is_connected = False



    ### Flight Methods ###

    def default_fly_to(self, x, y, results_folder):
        logging.debug('DroneController: Instructed to move to : (' + str(x) + ',' + str(y) + ')')
        logging.debug('Connecting to the crazyflie')
        crazyflie = self.connect_to_crazyflie()

        logging.debug('DroneController: Setting up the variable logging')
        self.setup_logging(crazyflie, results_folder)

        # We take off when the commander is created
        with MotionCommander(crazyflie) as mc:
            # Allowing the drone to take off
            time.sleep(1)
            # Flying forward the Y amount
            if y != 0:
                mc.forward(y)
                time.sleep(1)
            # Flying to the right for the X amount
            if x != 0:
                mc.right(x)
                time.sleep(1)
            mc.stop()
            # Landing occurs when the Motion Commander goes out of scope
        # Here we are keeping the application alive as the Crazyflie library makes
        # non blocking calls
        while self.is_connected:
            time.sleep(1)

    def accleration_adjusted_flight(self, x, y, results_folder):
        # The speed at which the drone will fly. This value is the default as set in the API
        flight_speed = 0.2
        # The amount of time we want to add in order to account for acceleration and deceleation
        motor_change_buff = 0.04

        # Mimicking the time calculation that would be carried out in the API
        # First for the x dimension
        new_x_distance = 0
        if not x == 0:
            x_time = x / flight_speed
            # Calculating adjustment for air resistance

            # Adding the time to accelerate and declerate along with 10% boost
            x_time = (x_time * 0.1) + x_time + motor_change_buff 
            # Now we calculate the distance
            new_x_distance = flight_speed * x_time

        # Caclulating the same for y
        new_y_distance = 0
        if not y == 0:
            y_time = y / flight_speed
            # Adding the time to accelerate and declerate along with 10% boost
            y_time = (y_time * 0.1) + y_time + motor_change_buff 
            # Now we calculate the distance
            new_y_distance = flight_speed * y_time
        
        # Telling the drone to fly this distance
        self.default_fly_to(new_x_distance, new_y_distance, results_folder)
        
    def location_guided_flight(self, x, y, results_folder):
        logging.debug('DroneController: Instructed to move to : (' + str(x) + ',' + str(y) + ')')
        logging.debug('Connecting to the crazyflie')
        crazyflie = self.connect_to_crazyflie()

        logging.debug('DroneController: Setting up the variable logging')
        self.setup_logging(crazyflie, results_folder)

        # We take off when the commander is created
        with MotionCommander(crazyflie) as mc:

            remaining_x = x
            remaining_y = y

            # Calculating the limits of flght
            ninety_five_of_distance_x = x * 0.95
            ninety_five_of_distance_y = y * 0.95

            # We carry out a max of 3 attempts
            for x in range(3):
                # Allowing the drone to take off
                time.sleep(1)
                # Flying forward the Y amount
                if y != 0:
                    mc.forward(remaining_x)
                    time.sleep(1)
                # Flying to the right for the X amount
                if x != 0:
                    mc.right(remaining_y)
                    time.sleep(1)
                # Nested if statements are used as conditions are quite long
                if DroneController.state_estimate_x >= ninety_five_of_distance_x:
                    if DroneController.state_estimate_y >= ninety_five_of_distance_y:
                        break

        # Landing occurs when the Motion Commander goes out of scope
        # Here we are keeping the application alive as the Crazyflie library makes
        # non blocking calls
        while self.is_connected:
            time.sleep(1)