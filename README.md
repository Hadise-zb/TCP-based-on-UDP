# TCP-based-on-UDP
1. Implementation of TCP protocol using UDP.
2. Support Dupack-based re-transmission and Timeout-based re-transmission. 
3. Support Congestion control.
# To run
python3 receiver.py receiver_port FileReceived.txt

python3 sender.py receiver_host_ip receiver_port FileToSend.txt MWS MSS timeout pdrop seed
