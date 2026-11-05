# RDT 3.0 over UDP

A Python implementation of the RDT 3.0 reliable data transfer protocol for the CPS4222 networking laboratory.

The project uses UDP sockets to demonstrate reliable delivery when DATA packets or acknowledgements are lost or corrupted.

## Features

- Stop-and-wait transmission with alternating sequence numbers 0 and 1.
- A 16-bit one's-complement checksum with end-around carry.
- ACK validation and duplicate DATA detection.
- Timeout retransmission without a retry limit.
- Console output showing sender transitions S0–S9 and receiver transitions R0–R3.
- Five selectable transmission scenarios.

The implementation uses basic Python control flow, functions, and standard libraries.

## Files

- `sender.py`: Sends AAA, BBB, and CCC, validates ACKs, and retransmits after timeout.
- `receiver.py`: Checks incoming DATA, delivers valid messages, and returns ACKs.

## Requirements

Python 3 is required. The project was tested with Python 3.13.9.

No third-party packages are needed.

## How to Run

Open two separate terminals in the project directory.

In the first terminal, start the receiver:

```bash
python receiver.py
```

Choose one test scenario:

```text
1 = Normal transmission
2 = Data loss
3 = Data corruption
4 = ACK loss
5 = ACK corruption
```

After the receiver displays `RECEIVER READY`, start the sender in the second terminal:

```bash
python sender.py
```

Wait until the sender reports that all three messages were acknowledged. Then press Ctrl+C in the receiver terminal to stop it.

For each new test, restart the receiver and run the sender once.

When using Spyder, run the two scripts in separate IPython consoles. After the sender finishes, select the receiver console and use **Interrupt kernel**.

## Configuration

The default receiver address is `127.0.0.1:12000`. The sender's retransmission timeout is 1 second.

To change the receiver address or port, update the corresponding settings in both scripts.

## Test Scenarios

1. **Normal transmission:** No fault is introduced.
2. **Data loss:** The first DATA packet is discarded.
3. **Data corruption:** The first DATA message is changed without updating its checksum.
4. **ACK loss:** The first ACK is discarded.
5. **ACK corruption:** The first ACK is sent with an incorrect checksum.

Each fault scenario introduces its fault once per receiver run.

## Results and Protocol Behavior

All five recorded tests delivered AAA, BBB, and CCC in order exactly once. Normal transmission required three DATA transmissions. Each fault scenario required four, including one timeout retransmission.

The sender retransmits the saved DATA packet when its timer expires. A corrupted or wrong-number ACK does not restart the timer. The sequence number changes only after a valid expected ACK arrives.

The receiver acknowledges duplicate DATA without delivering it again. It remains running after receiving three messages so that it can acknowledge possible retransmissions.
