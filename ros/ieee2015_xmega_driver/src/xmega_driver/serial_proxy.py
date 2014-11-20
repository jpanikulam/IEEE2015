#!/usr/bin/python
from __future__ import division # Make all division floating point division

# Misc
import os
import threading
import time

# Package stuff
from .parse_types import parse_types_file

# Serial
import serial
from collections import deque
import string

# Math
import numpy as np

lock = threading.Lock()
default_path_to_types = os.path.join('..', '..', '..', '..', 'xmega', 'types.h')


def thread_lock(function_to_lock):
    '''thread_lock(function) -> locked function 
    Thread locking decorator
        If you use this as a decorator for a function, it will apply a threading lock during the execution of that function,
        Which guarantees that no ROS callbacks can change the state of data while it is executing. This
            is critical to make sure that a new message being sent doesn't cause a weird serial interruption
    '''
    def locked_function(*args, **kwargs):
        # Get threading lock
        lock.acquire()
        # Call the decorated function as normal with its input arguments
        result = function_to_lock(*args, **kwargs)
        # Release the lock
        lock.release()
        # Return, pretending the function hasn't changed at all
        return result
    # Return the function with locking added
    return locked_function


class Serial_Proxy(object):
    def __init__(self, port, baud_rate, types_path=default_path_to_types, verbose=True):
        '''Superclass for XMega communication
        Purpose: Communicate with an XMega via serial link
        Arguments:
            - port: Serial port to attach to
            - baud_rate: Serial baud rate
            - types_path: Path to the types.h file in jOS.h (Should be the xmega folder)
            - verbose: Decide whether or not to print information messages

        Function:
            Read (Messages FROM Xmega):
                Loop permanently, listening for a serial message - interpret that message based on
                 predetermined parameters defined in the message type, defined in [1] and described
                 in its readme.
                Once a message of known type is recieved, it is called from the callback_dict
                 In a practical sense, to add a function to the action dict one should use bind_xmega_callback_function
                 to bind a function to a message type.

            Write (Messages TO Xmega):
                Silently listen for something published on the ROS message listener topic
                The ROS message is composed of a type and a data field - defined in [2]
                 'type' determines the action (also called message type), and the data field
                 generally is the exact number that will be sent to the xmega. 
                
            The callback_dict maps the hex message type to the function that should be called when a message
             of that type is recieved.
        Underdefined:
            - How the length of an outgoing message is determined from a ROS Topic

        Notes:
            This was designed to work with the communication protocol as we defined it. It does not do anything that relies
            on the specific XMega-side implementation of the protocol.

            At some point, we should consider building a simpler XMega implementation of the protocol, which relies less on malloc
            Proposal: Each item defines its own message length independent of the defined type. OR: The type field fully encodes 
                length (0-255 bytes)
                -- Would this improve things?

        TODO:
            -(DONE) Adding a simple internal message queue could resolve some thread-lock message loss issues. Need to test more extensively 
             to see whether or not this is an issue
            - Add the ability to configure multiple timed loops
            - Check that the incoming messages are of the appropriate length (i.e. nobody is trying to pass a message longer
                than its byte type specifies)

        Unhandled Errors:
            - Sudden unplugging of the USB

        Bibliography:
            [1] https://github.com/ufieeehw/IEEE2015/tree/master/xmega
            [2] https://github.com/ufieeehw/IEEE2015/tree/master/ros/ieee2015_xmega_driver/msg
        '''
        self.verbose = verbose

        try:
            self.serial = serial.Serial(port, baud_rate, )#timeout=0.01)
        except(serial.serialutil.SerialException), e:
            raise(
                Exception("Serial_Proxy could not open port " + port + 
                    "\nIf you have the Xmega plugged in, try setting up the Udev rules\n", e
                )
            )
        except(IOError):
            self.err_log("Could not attach by baud rate - trying to use socat...")
            self.serial = serial.Serial(port)

        # Mapping from hex to string values, will by populated by bind_types
        # self.string_to_hex = {}  # Used for messages going to xmega
        self.incoming_msg_types = {}  # Used for messages coming from xmega

        # Defines which action function to call on the received data
        self.callback_dict = {}
        # Defines the relationship between poll_message names and the hex name
        self.outgoing_msg_types = {
            'example_poll_msg': '0F'
        }

        # First two bits determine the length of the message
        self.byte_type_defs = {}  # This will be populated by self.bind_types

        self.message_queue = deque()

    def err_log(self, *args):
        '''Print the inputs as a list if class verbosity is True'''
        if self.verbose:
            print ['Xmega LOG:'], string.join(map(str, args))

    def send_keep_alive(self):
        '''Send a keep-alive message
        Critically, this includes a threading lock'''
        self.add_message('keep_alive')

    def run_serial_loop(self):
        read_loop = threading.Thread(target=self._read_loop)
        write_loop = threading.Thread(target=self._write_loop)
        read_loop.daemon = True
        write_loop.daemon = True
        write_loop.start()
        read_loop.start()

    def _write_loop(self):
        print("At start of write loop!")
        # Initialize time
        old_time = time.time()
        while True:
            # Timed watchdog messages every 0.5 sec
            cur_time = time.time()
            if (cur_time - old_time) > 0.5:
                old_time = cur_time
                self._write_packet('keep_alive')

            # Handle ONE outgoing message
            if len(self.message_queue) > 0:
                outgoing_msg = self.message_queue.popleft()
                self._write_packet(*outgoing_msg)  # "*" unpacks touple(_type, msg) into two arguments

    def _read_loop(self):
        '''read_packets
        Function:
            Permanently loops, waiting for serial messages from the XMega, and then calls 
             the appropriate action function
        Notes:
            - This does not handle desynchronization with the microcontroller
            - This does not adequately handle microcontroller errors
            - I anticipate that there might be blocking issues relating to serial.read
            - There may be problems with high-volume messaging because the callback functions 
               may take much time to execute
        '''
        type_length = 1  # Bytes
        length_length = 1  # Bytes
        type_mask =  0b11000000
        error_mask = 0b00110000

        while True:
            print("At start of read loop!")
            # Handle the first byte, determining type
            unprocessed_type = self.serial.read(type_length)
            self.err_log("Simple outgoing type ", unprocessed_type)
            msg_type = ord(unprocessed_type)
            msg_byte_type = msg_type & type_mask
            b_error = (msg_type & error_mask) == error_mask
            self.err_log('Recieving message of type', msg_type)

            # Message of known length
            if msg_byte_type in self.byte_type_defs.keys():
                msg_length = self.byte_type_defs[msg_byte_type]
                print msg_length, type(msg_length)

                # Poll message (zero length)
                if msg_length == 0:
                    msg_data = None

                # Defined byte length messages
                elif msg_length > 0:
                    msg_data = self.serial.read(msg_length)

                # N-Byte Message
                elif msg_length is None:
                    callback_function = self.callback_dict[msg_type]
                    self.err_log('Recognized type as', callback_function.__name__)

                    msg_length = self.serial.read(length_length)
                    msg_data = self.serial.read(msg_length)
                    self.err_log("Message content:", msg_data)
                    callback_function(msg_data)
                    
                if msg_type in self.callback_dict.keys():
                    callback_function = self.callback_dict[msg_type]
                    callback_function(msg_data)
                else:
                    self.err_log("No callback function for ", msg_type)

            # Failure
            else:
                self.err_log('Did not recognize type', msg_type)

    def add_message(self, _type, data=None):
        '''add_message(_type, data=None)
        Add a message to the messaging queue. Use this when you want to send a message
        '''

        self.message_queue.append((_type, data))

    def _write_packet(self, _type, data=None):
        '''write_packet(self, _type, data=None)
        Function:
            This [effectively] listens to ROS messages on either the
        Notes:
            type is _type because "type" is a python protected name
        '''
        self.err_log("Readying to send message of type ", _type)
        if _type in self.outgoing_msg_types.keys():
            self.err_log("Write type recognized as a polling message")
            write_data = self.outgoing_msg_types[_type]
            self.err_log("Writing as ", write_data)
            self.serial.write(chr(write_data))
            if data is not None:
                self.err_log("Data, ")
                for character in data:
                    self.err_log("writing character ", character)
                    self.serial.write(character)
            else:
                self.err_log("No other data to write")
        else:
            self.err_log("Write type not recognized")

    def bind_callback(self, msg_type, function):
        '''All messages of type $msg_type recieved from the xmega will be sent to the function $function
        The function will be called such that its argument is the data content of the message.

        This means that for a poll message, the argument will be None, for a message of predefined length, the 
         argument will be a string of everything after the type identifier, and for an N-Byte message, the argument will be 
         everything after the length token.
        '''
        if msg_type in self.incoming_msg_types.keys(): # Check that the message type is known
            self.callback_dict.update(
                {
                    self.incoming_msg_types[msg_type]: function
                }
            )
        else:
            raise(Exception("Type " + msg_type + " is not known to the serial proxy, have you bound types?"
                "\n This Error may be caused by not indicating the correct path to the types.h file in the "
                "serial_proxy initialization, or by having a malformed types.h file"))

    def bind_types(self, types_path):
        '''bind_types -> types
        Purpose: 
            Given a types_path (the relative path to the 'types.h' file in the xmega folder), this will automatically
             parse that file and figure out the relationships between string type names and their corresponding hex names
             An example of such a relationship is 'poll_imu': 0x01 or 'special_message': 0xF0.

            The reason this was done was to avoid having to explicitly declare that '0xC0' (Something very much subject to change)
             was related to a particular function or sensor. Instead, someone can indirectly refer to something more abstract, such as
             'poll_imu', this way we can change the behavior of the ROS end OR the XMega end message naming without seriously affecting 
             the other.

        Examples:
        Here is an example of what the output of parse_types might look like.
        types = [
            {'msg_length': ' 0', 'type_name': 'NO_DATA_TYPE', 'hex_name': '0x00'}
            {'msg_length': ' 1', 'type_name': 'DATA_1B_TYPE', 'hex_name': '0x40'}
            {'msg_length': ' 2', 'type_name': 'DATA_2B_TYPE', 'hex_name': '0x80'}
            {'msg_length': ' None', 'type_name': 'DATA_NB_TYPE', 'hex_name': '0xC0'}
            {'type_name': 'ERROR_MASK', 'mask': ' error', 'hex_name': '0x30'}
            {'type_name': 'KILL_TYPE', 'out': ' kill', 'hex_name': '0x01'}
            {'type_name': 'START_TYPE', 'out': ' start', 'hex_name': '0x02'}
            {'type_name': 'KEEP_ALIVE_TYPE', 'out': ' keep_alive', 'hex_name': '0x03'}
            {'type_name': 'IMU_NOTIFY_TYPE', 'out': ' poll_imu', 'hex_name': '0x04'}
        ]

        '''
        types = parse_types_file(types_path)
        for _type in types:
            if 'in' in _type.keys():
                self.incoming_msg_types.update(
                    {_type['in']: _type['hex_name']}
                )
            if 'out' in _type.keys():
                self.outgoing_msg_types.update(
                    {_type['out']: _type['hex_name']}
                )
            if 'msg_length' in _type.keys():
                self.byte_type_defs.update(
                    {_type['hex_name']: _type['msg_length']}
                )
