import threading
import time
from datetime import datetime
import base64
import json
import requests
from urllib3.exceptions import InsecureRequestWarning
from influxdb import InfluxDBClient
import json
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
import socket

token = ''



# login_uri = 'http://192.168.100.104:9907/login'
# add_readings_uri = 'http://192.168.100.104:9907/reports/addReadingsList'
login_uri = 'https://iot.skarpt.net/java_bk/login'
add_readings_uri = 'https://iot.skarpt.net/java_bk/reports/addReadingsList'

with open('/data/options.json', 'r') as config_file:    config = json.load(config_file)

# Get the username and password from the configuration
userName = config.get('username')
password = config.get('password')

print(f"Username: {userName}")
print(f"Password: {password}")



DATABASE_PORT = config.get('database_port', '8086')  # Default to '8086' if not set
USERNAME_DATABASE = config.get('username_database', 'default_username')
PASSWORD_DATABASE = config.get('password_database', 'default_password')
INTERNAL_BACKUP_DATABASE_NAME = config.get('internal_backup_database_name', 'default_backup_db')
INTERNAL_DATABASE_NAME = config.get('internal_database_name', 'default_internal_db')
DATABASE_IP = config.get('database_ip', '127.0.0.1')
measurement = config.get('measurement', 'default_measurement')

print("Database Port:", DATABASE_PORT)
print("Username:", USERNAME_DATABASE)
print("Password:", PASSWORD_DATABASE)
print("Backup DB Name:", INTERNAL_BACKUP_DATABASE_NAME)
print("Internal DB Name:", INTERNAL_DATABASE_NAME)
print("Database IP:", DATABASE_IP)
print("Measurement:", measurement)




def http_request(url, method, headers, timeout=30, body=None):
    try:
        result = requests.request(method=method, url=url, verify=False, headers=headers, json=body, timeout=timeout)
        return result
    except Exception as ex:
        print(ex.__cause__)
        return False


def login():
    global token
    basic_auth = userName + ':' + password
    encoded_u = base64.b64encode(basic_auth.encode()).decode()
    header = {"Authorization": "Basic %s" % encoded_u}
    result = http_request(url=login_uri,
                          method='get',
                          headers=header)

    if not result:
        print(result)
        print("error on login")
        print(result.content)
        return
    print(result.content)
    json_string = result.content.decode('utf8').replace("'", '"')
    json_object = json.loads(json_string)
    token = json_object['entity'][0]['token']
    print(token)
    return token


def SendJsonToServer(json_object):
    global token
    try:
        if token == "":
            token = login()
        result = http_request(url=add_readings_uri,
                              method='post',
                              body=json_object,
                              headers={"TOKEN": token})
        if not result:
            print(result)
            print("error on sending")
            print(result.content)
            return False
        print(result.content)
        if result.status_code != 200:
            token = login()
            result = http_request(url=add_readings_uri,
                                  method='post',
                                  body=json_object,
                                  headers={"TOKEN": token})
            if not result:
                print(result)
                print("error on sending")
                print(result.content)
                return False
            print(result.content)
            if result.status_code != 200:
                return False
    except Exception as exc:
        print("ERROR : %s" % exc)
        return False
    return True


def ConvertRTCtoTime(RTC):
    Year, Month, Day, Hours, Min, Sec = RTC[0:2], RTC[2:4], RTC[4:6], RTC[6:8], RTC[8:10], RTC[10:12]
    Year, Month, Day, Hours, Min, Sec = int(Year, 16), int(Month, 16), int(Day, 16), int(Hours, 16), int(Min, 16), int(
        Sec, 16)
    print("Date is ", Year, "/", Month, "/", Day)
    print("Time is ", Hours, "/", Min, "/", Sec)
    Date = str(Year) + "/" + str(Month) + "/" + str(Day)
    Time = str(Hours) + "/" + str(Min) + "/" + str(Sec)
    # return  Year, Month, Day, Hours, Min, Sec
    return Date, Time


def TempFun(temp):
    sign = ''
    hexadecimal = temp
    end_length = len(hexadecimal) * 4
    hex_as_int = int(hexadecimal, 16)
    hex_as_binary = bin(hex_as_int)
    padded_binary = hex_as_binary[2:].zfill(end_length)
    normalbit = padded_binary[0]
    postitive = padded_binary[1]
    value = padded_binary[2:]
    if str(normalbit) == '0':
        pass
    else:
        return "Sensor error"

    if str(postitive) == '0':
        sign = '+'
    else:
        sign = '-'

    if sign == '+':
        return str(int(value, 2) / 10)

    else:
        return "-" + str(int(value, 2) / 10)


def HumFun(hum):
    hexadecimal = hum
    end_length = len(hexadecimal) * 4
    hex_as_int = int(hexadecimal, 16)
    hex_as_binary = bin(hex_as_int)
    padded_binary = hex_as_binary[2:].zfill(end_length)
    normalbit = padded_binary[0]
    value = padded_binary[1:]
    if str(normalbit) == '0':
        pass
    else:
        return "Sensor error"
    return str(int(value, 2))


def ConvertPacketToReadings(packet):
    # Initialize variables
    Sensorhexlist = []
    sensorfound = False
    NumberOfSensors = 0

    # Extract gateway details from packet

    Packetsensorlength = packet[76:80]

    # Return if there are no sensors found
    if Packetsensorlength == "0000":
        return 0
    if int(Packetsensorlength, 16) != 0:
        sensorfound = True
        NumberOfSensors = int(packet[82:84], 16)

        result = 0
        for i in range(NumberOfSensors):
            i = i + result
            Sensorhexlist.append(packet[86 + i:108 + i])
            result += 21

    # Extract gateway information
    GatwayId = packet[24:40]
    RTC = packet[40:52]
    date, time = ConvertRTCtoTime(RTC)

    GatewayBattary = int(packet[68:72], 16) / 100
    GatewayPower = int(packet[72:76], 16) / 100

    # Create the JSON object
    json_object = {
        "GatewayId": GatwayId,
        "GatewayBattary": GatewayBattary,
        "GatewayPower": GatewayPower,
        "Date": date,
        "Time": time,
        "packet": packet
    }

    readings = []
    for sensor_packet in Sensorhexlist:
        sensor_data = {
            "Sensorid": sensor_packet[0:8],
            "SensorBattary": int(sensor_packet[10:14], 16) / 1000,
            "temperature": TempFun(sensor_packet[14:18]),
            "humidity": HumFun(sensor_packet[18:20])
        }
        readings.append(sensor_data)
        print(f"sensor {sensor_packet[0:8]} :", json_object)

    # Add readings to the main JSON object
    json_object["data"] = readings
    print(sensorfound, NumberOfSensors, Sensorhexlist)

    # Send to the server
    if not SendJsonToServer(json_object):
        return False

    return True


def Send_Saved_Database():
    client = InfluxDBClient(DATABASE_IP, DATABASE_PORT, USERNAME_DATABASE, PASSWORD_DATABASE,
                            INTERNAL_BACKUP_DATABASE_NAME)
    result = client.query('SELECT *  FROM ' + str(INTERNAL_BACKUP_DATABASE_NAME) + '."autogen".' + str(measurement))
    data = list(result.get_points())
    for point in data:
        success = False  # Initialize the success flag

        # Attempt to convert sensor data and send it to the server
        success = ConvertPacketToReadings(str(point["Packet"]))

        if success:
            # Only delete the packet if the conversion and sending were successful
            client.delete_series(database=INTERNAL_BACKUP_DATABASE_NAME, measurement=measurement,
                                 tags={"id": point["id"]})
            print(f"Packet with id {point['id']} sent and deleted successfully.")
        else:
            # Log failure and retry after a delay
            print(f"Failed to send packet with id {point['id']}. Retrying in 5 seconds...")
            # Wait for 5 seconds before retrying


def test_server_connection(domain, port=5029, timeout=5):
    try:
        # Attempt to establish a socket connection to the server
        server_ip = socket.gethostbyname(domain)
        socket.create_connection((server_ip, port), timeout)
        print(f"Connection to {domain} on port {port} successful.")
        return True
    except (socket.gaierror, socket.timeout, ConnectionRefusedError, OSError) as e:
        if isinstance(e, OSError) and e.errno == 101:
            print(f"Network is unreachable: {e}")
        else:
            print(f"Connection to {domain} failed: {e}")
        return False


def Checked_SavedHolding_Database():
    client = InfluxDBClient(DATABASE_IP, DATABASE_PORT, USERNAME_DATABASE, PASSWORD_DATABASE,
                            INTERNAL_BACKUP_DATABASE_NAME)
    result = client.query('SELECT *  FROM ' + str(INTERNAL_BACKUP_DATABASE_NAME) + '."autogen".' + str(measurement))
    length = len(list(result.get_points()))
    if length != 0:
        return True
    else:
        return False

def logic():
    while True:
        # Test server connection before every operation
        if test_server_connection('iot.skarpt.net'):
            token = login()  # Attempt to log in and get a token
            if token:  # Only proceed if login is successful
                # Check if there are packets in the holding database
                if Checked_SavedHolding_Database():
                    # Send saved packets in a separate thread
                    thread = threading.Thread(target=Send_Saved_Database)
                    thread.start()
                    thread.join()  # Ensure the thread completes before proceeding
            else:
                print("Login failed, retrying in 5 seconds...")
                time.sleep(30)
        else:
            print("Server error, retrying in 5 seconds...")
            time.sleep(30)
        time.sleep(10)

        



# Start the logic
logic()
