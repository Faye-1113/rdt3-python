import socket
import json


RECEIVER_IP = "127.0.0.1"
RECEIVER_PORT = 12000
POLL_SECONDS = 0.5


# Step 1: Calculate a 16-bit one's-complement checksum.
def checksum_bytes(data_bytes):
    data_length = len(data_bytes)

    if data_length % 2 != 0:
        data_bytes = data_bytes + b"\x00"
        data_length = len(data_bytes)

    total = 0

    for position in range(0, data_length, 2):
        high_byte = data_bytes[position]
        low_byte = data_bytes[position + 1]
        word = high_byte * 256 + low_byte
        total = total + word

        while total > 65535:
            carry = total // 65536
            lower_bits = total % 65536
            total = lower_bits + carry

    checksum = 65535 - total
    return checksum


def calculate_checksum(pac_type, seq_num, message):
    sequence_text = str(seq_num)
    packet_text = pac_type + "|" + sequence_text + "|" + message
    data_bytes = packet_text.encode("utf-8")
    checksum = checksum_bytes(data_bytes)
    return checksum


# Step 2: Create each packet field separately.
def create_packet(pac_type, seq_num, message):
    packet = {}
    packet["type"] = pac_type
    packet["sequence"] = seq_num
    packet["message"] = message
    checksum = calculate_checksum(pac_type, seq_num, message)
    packet["checksum"] = checksum
    return packet


def convert_packet_to_bytes(packet):
    packet_text = json.dumps(packet)
    packet_bytes = packet_text.encode("utf-8")
    return packet_bytes


# Step 3: Check packet format before reading its fields.
def convert_bytes_to_packet(raw_data):
    try:
        packet_text = raw_data.decode("utf-8")
        packet = json.loads(packet_text)
    except UnicodeDecodeError:
        return None
    except json.JSONDecodeError:
        return None

    if type(packet) != dict:
        return None
    if "type" not in packet:
        return None
    if "sequence" not in packet:
        return None
    if "message" not in packet:
        return None
    if "checksum" not in packet:
        return None
    if len(packet) != 4:
        return None

    if type(packet["type"]) != str:
        return None
    if packet["type"] != "DATA":
        if packet["type"] != "ACK":
            return None

    if type(packet["sequence"]) != int:
        return None
    if packet["sequence"] != 0:
        if packet["sequence"] != 1:
            return None

    if type(packet["message"]) != str:
        return None
    if type(packet["checksum"]) != int:
        return None
    if packet["checksum"] < 0:
        return None
    if packet["checksum"] > 65535:
        return None
    return packet


# Step 4: Recalculate and compare the checksum explicitly.
def is_packet_corrupt(packet):
    pac_type = packet["type"]
    seq_num = packet["sequence"]
    message = packet["message"]
    received_checksum = packet["checksum"]
    correct_checksum = calculate_checksum(pac_type, seq_num, message)

    if received_checksum == correct_checksum:
        return False
    else:
        return True


def receive_packet(udp_socket, wait_seconds):
    udp_socket.settimeout(wait_seconds)
    try:
        result = udp_socket.recvfrom(4096)
        return result
    except BlockingIOError:
        return None
    except socket.timeout:
        return None
    finally:
        udp_socket.settimeout(None)

def main(test_choice=None, receiver_port=RECEIVER_PORT):
    # Step 5: Select one channel fault for this experiment.
    if test_choice is None:
        print("1 = Normal transmission")
        print("2 = Data loss")
        print("3 = Data corruption")
        print("4 = ACK loss")
        print("5 = ACK corruption")
        test_choice = input("Enter test situation (1-5): ").strip()

    if test_choice == "1":
        situation = "normal"
    elif test_choice == "2":
        situation = "data_loss"
    elif test_choice == "3":
        situation = "data_corruption"
    elif test_choice == "4":
        situation = "ack_loss"
    elif test_choice == "5":
        situation = "ack_corruption"
    else:
        print("ValueError: Please choose 1, 2, 3, 4 or 5.")
        return

    exp_seq_num = 0
    rec_messages = []
    fault_used = False
    rec_soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        rec_soc.bind((RECEIVER_IP, receiver_port))
        print()
        print("Situation:", situation)
        print("RECEIVER READY")

        while True:
            result = receive_packet(rec_soc, POLL_SECONDS)
            if result is None:
                continue
            raw_data = result[0]
            send_addr = result[1]
            packet = convert_bytes_to_packet(raw_data)

            print()

            corrupt = True
            if packet is not None:
                corrupt = is_packet_corrupt(packet)
                if corrupt == False:
                    if packet["type"] != "DATA":
                        corrupt = True

            if corrupt == False:
                if fault_used == False:
                    if situation == "data_loss":
                        fault_used = True
                        print("SIMULATED DATA LOSS: discard this packet.")
                        continue
                    elif situation == "data_corruption":
                        fault_used = True
                        packet["message"] = packet["message"] + "X"
                        print("SIMULATED DATA CORRUPTION: keep the old checksum.")
                        corrupt = is_packet_corrupt(packet)

            # Step 6: Handle the state "Wait for 0 from below".
            if exp_seq_num == 0:
                if corrupt == True:
                    transition = "R3"
                    ack_num = 1
                    print("R3: corrupt DATA; repeat ACK 1.")
                elif packet["sequence"] == 1:
                    transition = "R3"
                    ack_num = 1
                    print("R3: duplicate DATA 1; repeat ACK 1.")
                else:
                    transition = "R0"
                    message = packet["message"]
                    rec_messages.append(message)
                    print("R0: correct DATA 0.")
                    print("DELIVER:", message)
                    ack_num = 0

            # Step 7: Handle the state "Wait for 1 from below".
            elif exp_seq_num == 1:
                if corrupt == True:
                    transition = "R1"
                    ack_num = 0
                    print("R1: corrupt DATA; repeat ACK 0.")
                elif packet["sequence"] == 0:
                    transition = "R1"
                    ack_num = 0
                    print("R1: duplicate DATA 0; repeat ACK 0.")
                else:
                    transition = "R2"
                    message = packet["message"]
                    rec_messages.append(message)
                    print("R2: correct DATA 1.")
                    print("DELIVER:", message)
                    ack_num = 1

            # Step 8: Create the ACK, then pass it through the faulty channel.
            ack_packet = create_packet("ACK", ack_num, "")
            if fault_used == False and situation == "ack_loss":
                fault_used = True
                print("SIMULATED ACK LOSS: do not send this ACK.")
            elif fault_used == False and situation == "ack_corruption":
                fault_used = True
                bad_checksum = ack_packet["checksum"] + 1
                if bad_checksum > 65535:
                    bad_checksum = 0
                ack_packet["checksum"] = bad_checksum
                ack_bytes = convert_packet_to_bytes(ack_packet)
                rec_soc.sendto(ack_bytes, send_addr)
                print("SIMULATED ACK CORRUPTION: send a wrong checksum.")
            else:
                ack_bytes = convert_packet_to_bytes(ack_packet)
                rec_soc.sendto(ack_bytes, send_addr)
                print("Send ACK", ack_num)

            # Step 9: Switch the expected bit only after a new delivery.
            if transition == "R0":
                exp_seq_num = 1
            elif transition == "R2":
                exp_seq_num = 0
            # R1 and R3 leave the expected bit unchanged.

            if transition == "R0" or transition == "R2":
                if len(rec_messages) == 3:
                    print()
                    print("ALL THREE MESSAGES DELIVERED:", rec_messages)
                    print("Keep listening for retransmissions.")
                    print("Stop this receiver after sender.py finishes.")

    except KeyboardInterrupt:
        print()
        print("RECEIVER STOPPED")
        print("Messages delivered:", rec_messages)
    finally:
        rec_soc.close()
        print("Receiver socket closed.")

    return rec_messages


if __name__ == "__main__":
    main()
