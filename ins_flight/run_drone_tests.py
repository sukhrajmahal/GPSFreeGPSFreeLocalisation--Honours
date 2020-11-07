import logging
import os
import sys
from datetime import datetime
import sqlite3

from drone_controller import DroneController

def setup_output_folder(output_folder, algorithm, x_name, y_name, num_samples):
    # Checking the algorithm folder exists
    result_folder = output_folder + "/" + algorithm + "/X-" + x_name + "/Y-" + y_name + "/numSamples-" + str(num_samples) + "/"
    logging.debug("Script: Results folder will be: " + result_folder)
    
    # If the folder does not already exist, we create the folder
    if not os.path.isdir(result_folder):
        os.makedirs(result_folder)
    return result_folder

def setup_database(database_file):
    database_connection = sqlite3.connect(database_file)
    database_cursor = database_connection.cursor()

    # Creating the results table
    database_cursor.execute('''CREATE TABLE IF NOT EXISTS results
                                (id INTEGER PRIMARY KEY AUTOINCREMENT, algorithm text, intendedX real, intendedY real, 
                                actualX real, actualY real, resultsFolder text)''')
    logging.debug("Script: Database has been created")
    return database_cursor

def create_database_entry(cursor, algorithm, intended_x, intended_y, actual_x, actual_y, results_folder):
    sql_request = '''INSERT INTO results (algorithm,intendedX,intendedY,actualX, actualY, resultsFolder)
                    VALUES ('%s', %s, %s, %s, %s, '%s')''' % (
        algorithm, intended_x, intended_y, actual_x, actual_y, results_folder)
    cursor.execute(sql_request)
    cursor.connection.commit()

def check_inputs():
    # Checking that the correct amount of command line parameters have been passed
    if len(sys.argv) != 3:
        print('Usage: python3 run_drone_tests.py <database file path> <sensor data output folder>')
        logging.error('Script: User did not provide the correct number of parameters. They provided: ' + str(sys.argv))
        exit()
    
    # Getting the database file
    database_file = sys.argv[1]
    logging.debug('Script: Database file provided: ' + database_file)

    # Getting the folder where debug and sensor data will be recorded
    output_folder = sys.argv[2]
    print(output_folder)
    logging.debug('Script: Output folder provided: ' + output_folder)

    # Checking that the output folder exists
    if not os.path.isdir(output_folder):
        print("The folder provided for sensor output does not exist.")
        logging.error("Script: Output folder does not exist. Exiting")
        exit()

    return (database_file, output_folder)

def main():
    # Setting up the logging file
    # Logging file will be called log-<runtime time and date>
    logging.basicConfig(filename='script_log-' + str(datetime.now()), level=logging.DEBUG)

    # Checking that script inputs are valid
    checked_args = check_inputs()
    database_file = checked_args[0]
    output_folder = checked_args[1]

    # Setting up the database
    database_cursor = setup_database(database_file)

    # Getting the drone controller
    drone_controller = DroneController()

    previous_x = ""
    previous_y = ""
    num_samples = 1

    # Getting the algorithm name
    algorithm = input("Algorithm Name: ")
    logging.debug("Script: Algorithm Name Provided: " + algorithm)
    logging.debug("Script: Entering Testing Loop")

    while True:
        # Reminding the user what the previous configuration was
        print("The previous configuration was: X: " + previous_x + " Y: " + previous_y + " Num Samples: "
              + str(num_samples))

        # Getting the X Distance to fly
        x_distance = input("How many metres in the X direction would you like to fly: ")
        if x_distance == "BREAK":
            break

        # Getting the Y Distance to fly
        y_distance = input("How many metres in the Y direction would you like to fly: ")
        if y_distance == "BREAK":
            break

        # If the same configuration was used, increase the numSamples
        if x_distance == previous_x and y_distance == previous_y:
            num_samples += 1
        else:
            num_samples = 1

        # Setting up the folders for sensor output
        results_folder = setup_output_folder(output_folder, algorithm, x_distance, y_distance, num_samples)

        # Commanding the drone to fly the given distances
        drone_controller.default_fly_to(int(x_distance), int(y_distance), results_folder)

        # Getting the actual distances of the flight
        x_actual = input("Actual X: ")
        if x_actual == "BREAK":
            break

        y_actual = input("Actual Y: ")
        if y_actual == "BREAK":
            break

        # Creating a database entry
        create_database_entry(database_cursor, algorithm, x_distance, y_distance,
                              x_actual, y_actual, results_folder)

        # Formatting Gap
        print()

        # Updating tracking variables
        previous_x = x_distance
        previous_y = y_distance

    # Closing the connection at the end
    database_cursor.connection.close()

if __name__ == '__main__':
    main()
