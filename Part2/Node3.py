# Node3
import struct

import numpy as np

from Part2.config.globalConfig import *
from Part2.frame.PHYFrame import *
from Part2.config.Type import *
from all_globals import *
from Part2.config.ACKConfig import *


def set_stream():
    asio_id = 14
    asio_in = sd.AsioSettings(channel_selectors=[0])
    asio_out = sd.AsioSettings(channel_selectors=[1])

    sd.default.extra_settings = asio_in, asio_out
    sd.default.device[0] = asio_id
    sd.default.device[1] = asio_id
    stream = sd.Stream(sample_rate, blocksize=2048, dtype=np.float32, callback=callback, channels=1)
    return stream


def callback(indata, outdata, frames, time, status):
    global global_buffer
    global global_pointer
    global global_status
    global TxFrame
    global is_noisy
    global_buffer = np.append(global_buffer, indata[:, 0])
    if np.average(np.abs(indata[:, 0]) > 0.005):
        is_noisy = True
    else:
        is_noisy = False
    if global_status == "":
        # when not sending, then receiving
        outdata.fill(0)

    if global_status == "send data":
        global global_input_index
        global TxFrame
        if len(TxFrame) - global_input_index > frames:
            outdata[:] = np.array(TxFrame[global_input_index:global_input_index + frames]).reshape(frames, 1)
        else:
            if len(TxFrame) - global_input_index >= 0:
                outdata[:] = np.append(TxFrame[global_input_index:],
                                       np.zeros(frames - len(TxFrame) + global_input_index)).reshape(frames, 1)
        global_input_index += frames

    if global_status == "sending ACK":
        global ACK_buffer
        global ACK_pointer
        global_status = ""
        outdata[:] = np.append(ACK_buffer[ACK_pointer], np.zeros(frames - len(ACK_buffer[ACK_pointer]))).reshape(frames,
                                                                                                                 1)
        ACK_pointer += 1


def gen_data(str_send, src_address, dest_address):
    frame = PhyFrame()
    frame.set_phy_load(MACFrame())
    frame.set_MAC_load(UDPFrame())
    frame.set_type(data_frame)
    frame.set_src_ip(translate_ip_to_bits(src_address[0]))
    frame.set_src_port(translate_port_to_bits(src_address[1]))
    frame.set_dest_ip(translate_ip_to_bits(dest_address[0]))
    frame.set_dest_port(translate_port_to_bits(dest_address[1]))
    frame.set_num(len(str_send)*8)
    byte_bit_str_buffer = ""
    for j in range(bytes_per_frame):
        if j < len(str_send):
            byte_bit_str_buffer += '{0:08b}'.format(ord(str_send[j]), 'b')
        else:
            byte_bit_str_buffer += "00000000"
    frame.set_load(byte_bit_str_buffer)
    frame.set_CRC()
    return frame


def send_athernet_data():
    global global_input_index
    global global_status
    global TxFrame
    global_input_index = 0
    while global_input_index < len(TxFrame):
        global_status = "send data"
    global_status = ""


def decode_ACK_bits(ACK_buffer):
    # first to convert all samples to bits
    str_decoded = ""
    pointer = 0
    ACK_length_in_bit = 20
    for i in range(ACK_length_in_bit):
        decode_buffer = ACK_buffer[pointer: pointer + samples_per_bin]
        if np.sum(decode_buffer * signal0) > 0:
            str_decoded += '0'
        else:
            str_decoded += '1'
        pointer += samples_per_bin
    return str_decoded


def check_ACK(range1, range2, data):
    """
    check if ACK received from range1 to range2
    retransmit frame if time out
    """
    global global_buffer
    global TxFrame
    global global_pointer
    while global_pointer < len(global_buffer):
        pointer_ACK = detect_preamble(global_buffer[global_pointer:global_pointer + 1024])
        if not pointer_ACK == 'error':
            global_pointer += pointer_ACK
            ACK_frame_array = global_buffer[global_pointer: global_pointer + 20 * samples_per_bin]
            ACK_frame = PhyFrame()
            ACK_frame.from_array(decode_ACK_bits(ACK_frame_array))
            if ACK_frame.check():
                if not ACK_confirmed[ACK_frame.get_decimal_num()]:
                    print("ACK ", ACK_frame.get_decimal_num(), " received!")
                    ACK_confirmed[ACK_frame.get_decimal_num()] = True
                ACK_confirmed[ACK_frame.get_decimal_num()] = True
            global_pointer += 48
        global_pointer += 1024
    global_pointer = len(global_buffer) >> 2
    res = True
    for i in range(range1, range2):
        if not ACK_confirmed[i]:
            res = False
            if time.time() - send_time[i] > retransmit_time and send_time[i] != 0:
                frame_retransmit[i] += 1
                if frame_retransmit[i] >= max_retransmit:
                    print("link error! exit")
                    exit(-1)
                else:
                    print("ACK ", i, " time out, time used: ", time.time() - send_time[i], ", retransmit")
                    # retransmit
                    TxFrame = data[i].get_modulated_frame()[:]
                    send_athernet_data()
                    send_time[i] = time.time()
                    TxFrame = []
                    res = False
    return res


def send_data(str_send):
    global TxFrame
    frame = gen_data(str_send, (node3_ip, node3_port), (NAT_athernet_ip, NAT_port))
    TxFrame = frame.get_modulated_frame()[:]
    send_athernet_data()
    TxFrame = []
    print("Node3 sending data finished")


def send_ACK(n_frame):
    global global_status
    global ACK_buffer
    global ACK_predefined
    ACK_buffer.append(ACK_predefined[n_frame])
    global_status = "sending ACK"


def receive_data():
    global TxFrame
    global global_buffer
    global global_pointer
    global detected_frames
    pointer = global_pointer
    byte_str = ""
    while True:
        if pointer + block_size > len(global_buffer):
            continue
        block_buffer = global_buffer[pointer: pointer + block_size]
        pointer_frame = detect_preamble(block_buffer)
        if not pointer_frame == "error":
            pointer += pointer_frame
            # detect a frame, first to check its correctness
            if pointer + frame_length - preamble_length > len(global_buffer):
                time.sleep(0.1)
            frame_detected = global_buffer[pointer: pointer + frame_length - preamble_length]
            frame_in_bits = decode_to_bits(frame_detected)
            # CRC correct, starting decode ip and port
            phy_frame = PhyFrame()
            phy_frame.from_array(frame_in_bits)
            pay_len = phy_frame.get_decimal_num()
            print("payload_length:", pay_len)
            byte_str = str(phy_frame.get_load())[0:pay_len]
            pointer += frame_length - preamble_length
            break
        pointer += block_size
    global_pointer = pointer
    byte_str = bit_load_to_str(byte_str)
    print("receiving data finished... showing contents...", byte_str)
    return byte_str


if __name__ == "__main__":
    stream = set_stream()
    stream.start()
    while True:
        str_in = input("Please input commands ")
        commands = [x for x in str_in.split(' ')]

        if commands[0] == "USER":
            send_data("USER")

            print(receive_data())

        elif commands[0] == "PASS":
            send_data("PASS")
            print(receive_data())

        elif commands[0] == "PWD":
            send_data("PWD")
            print(receive_data())

        else:
            break
    stream.stop()
