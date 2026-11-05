import socket
import json
import time


RECEIVER_IP = "127.0.0.1"
RECEIVER_PORT = 12000
TIMEOUT_SECONDS = 1.0
POLL_SECONDS = 0.5

WAIT_CALL_0 = "WAIT_CALL_0"
WAIT_ACK_0 = "WAIT_ACK_0"
WAIT_CALL_1 = "WAIT_CALL_1"
WAIT_ACK_1 = "WAIT_ACK_1"


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

def main(receiver_port=RECEIVER_PORT, timeout_seconds=TIMEOUT_SECONDS):
    messages = ["AAA", "BBB", "CCC"]
    next_message = 0
    seq_num = 0
    state = WAIT_CALL_0
    sndpkt = None
    start_time = None
    rec_addr = (RECEIVER_IP, receiver_port)
    send_soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        send_soc.bind(("", 0))
        print("SENDER STARTED")

        while (next_message < len(messages)
               or state == WAIT_ACK_0 or state == WAIT_ACK_1):

            # Step 5: Wait for application call 0.
            if state == WAIT_CALL_0:
                result = receive_packet(send_soc, 0.0)
                if result is not None:
                    address = result[1]
                    if address == rec_addr:
                        print("S9: ignore packet while waiting for call 0.")
                    continue

                # S0: make DATA 0, send it, and start the timer.
                message = messages[next_message]
                seq_num = 0
                data_packet = create_packet("DATA", seq_num, message)
                sndpkt = convert_packet_to_bytes(data_packet)
                send_soc.sendto(sndpkt, rec_addr)
                start_time = time.monotonic()
                state = WAIT_ACK_0
                next_message = next_message + 1
                print()
                print("S0: send DATA", seq_num, message, "; start timer.")

            # Step 6: Wait for application call 1.
            elif state == WAIT_CALL_1:
                result = receive_packet(send_soc, 0.0)
                if result is not None:
                    address = result[1]
                    if address == rec_addr:
                        print("S4: ignore packet while waiting for call 1.")
                    continue

                # S5: make DATA 1, send it, and start the timer.
                message = messages[next_message]
                seq_num = 1
                data_packet = create_packet("DATA", seq_num, message)
                sndpkt = convert_packet_to_bytes(data_packet)
                send_soc.sendto(sndpkt, rec_addr)
                start_time = time.monotonic()
                state = WAIT_ACK_1
                next_message = next_message + 1
                print()
                print("S5: send DATA", seq_num, message, "; start timer.")

            # Step 7: Wait for ACK 0.
            elif state == WAIT_ACK_0:
                current_time = time.monotonic()
                elapsed_time = current_time - start_time
                remaining_time = timeout_seconds - elapsed_time

                if remaining_time <= 0:
                    # S2: retransmit the saved bytes, without a retry limit.
                    send_soc.sendto(sndpkt, rec_addr)
                    start_time = time.monotonic()
                    print()
                    print("S2: timeout; resend SAME packet; restart timer.")
                    continue

                if remaining_time > POLL_SECONDS:
                    wait_seconds = POLL_SECONDS
                else:
                    wait_seconds = remaining_time
                result = receive_packet(send_soc, wait_seconds)
                if result is None:
                    continue

                ack_bytes = result[0]
                ack_address = result[1]
                if ack_address != rec_addr:
                    continue
                ack_packet = convert_bytes_to_packet(ack_bytes)

                # Check format, checksum, ACK type, and ACK number separately.
                correct_ack = False
                if ack_packet is not None:
                    corrupt = is_packet_corrupt(ack_packet)
                    if corrupt == False:
                        if ack_packet["type"] == "ACK":
                            if ack_packet["sequence"] == 0:
                                correct_ack = True

                if correct_ack == True:
                    # S3: stop the timer; next application data uses bit 1.
                    start_time = None
                    seq_num = 1
                    state = WAIT_CALL_1
                    print("S3: accept ACK 0; stop timer.")
                else:
                    # S1: do nothing; keep state and the original timer.
                    print("S1: ignore corrupt/wrong ACK; keep timer.")

            # Step 8: Wait for ACK 1.
            elif state == WAIT_ACK_1:
                current_time = time.monotonic()
                elapsed_time = current_time - start_time
                remaining_time = timeout_seconds - elapsed_time

                if remaining_time <= 0:
                    # S7: retransmit the saved bytes, without a retry limit.
                    send_soc.sendto(sndpkt, rec_addr)
                    start_time = time.monotonic()
                    print()
                    print("S7: timeout; resend SAME packet; restart timer.")
                    continue

                if remaining_time > POLL_SECONDS:
                    wait_seconds = POLL_SECONDS
                else:
                    wait_seconds = remaining_time
                result = receive_packet(send_soc, wait_seconds)
                if result is None:
                    continue

                ack_bytes = result[0]
                ack_address = result[1]
                if ack_address != rec_addr:
                    continue
                ack_packet = convert_bytes_to_packet(ack_bytes)

                correct_ack = False
                if ack_packet is not None:
                    corrupt = is_packet_corrupt(ack_packet)
                    if corrupt == False:
                        if ack_packet["type"] == "ACK":
                            if ack_packet["sequence"] == 1:
                                correct_ack = True

                if correct_ack == True:
                    # S8: stop the timer; next application data uses bit 0.
                    start_time = None
                    seq_num = 0
                    state = WAIT_CALL_0
                    print("S8: accept ACK 1; stop timer.")
                else:
                    # S6: do nothing; keep state and the original timer.
                    print("S6: ignore corrupt/wrong ACK; keep timer.")

        print()
        print("SENDER FINISHED: All three messages were acknowledged.")
        return True

    except KeyboardInterrupt:
        print()
        print("SENDER INTERRUPTED")
        return False
    finally:
        send_soc.close()
        print("Sender socket closed.")


if __name__ == "__main__":
    main()
