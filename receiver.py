# My python version is 2.7.13 on VNC.
import socket, re, time, threading, datetime, sys

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to the port
server_address = ('localhost', int(sys.argv[1]))
#print('starting up on {} port {}'.format(*server_address))
sock.bind(server_address)

# Sets a timeout on the server to 4 seconds
#sock.settimeout(4)

# Reads config file and sets status of heartbeat
#config = configparser.ConfigParser()
#config.read('opt.conf')

#
#logging.basicConfig(filename='handshakes.log', level=logging.INFO)

# Boolean to check if the first part of handshake is completed
firstpartofhandshakecompleted = False
firstpartofterminationcompleted = False
# Boolean to check if three-way handshake is successful
successful_connection = False

#
message_number = 0

# Sets client_address list as empty, so it can be checked if exception is thrown
client_address = ['0','0']

DEBUG = False
DEBUG2 = False

save_header = {}
save_header['seq_num'] = 0
save_header['ack_num'] = 0
save_header['ack_bit'] = 0
save_header['syn'] = 0
save_header['fin'] = 0

last_recieve_ack = 0
last_send_ack = 1

recieve_buffer = {}
lost_counter = 0

judge_lost = False

acked_seq = []

class Header:

    def __init__(self, seq_num, ack_num, ack_bit, syn, fin, data_size, judge_timeout):
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.ack_bit = ack_bit
        self.syn = syn
        self.fin = fin
        self.data_size = data_size
        self.judge_timeout = judge_timeout
	
    def bits(self):
        bits = '{0:032b}'.format(self.seq_num)
        bits += '{0:032b}'.format(self.ack_num)
        bits += '{0:01b}'.format(self.ack_bit)
        bits += '{0:01b}'.format(self.syn)
        bits += '{0:01b}'.format(self.fin)
        bits += '{0:032b}'.format(self.data_size)
        bits += '{0:01b}'.format(self.judge_timeout)

        return bits.encode()
    

def bits_to_header(bits):
    #bits = bits.decode()
    seq_num = int(bits[:32], 2)
    ack_num = int(bits[32:64], 2)
    ack_bit = int(bits[64], 2)
    syn = int(bits[65], 2)
    fin = int(bits[66], 2)
    data_size = int(bits[67:99], 2)
    judge_timeout = int(bits[99], 2)

    if (DEBUG):
        print("seq num: ", seq_num)
        print("ack num: ", ack_num)
        print("ack bit: ", ack_bit)
        print("syn: ", syn)
        print("fin: ", fin)
        print("judge_timeout: ", judge_timeout)

    return Header(seq_num, ack_num, ack_bit, syn, fin, data_size, judge_timeout)

def get_body_from_data(data):
	#data = data.decode()
	return data[100:]

def utf8len(s):
    return len(s.encode('utf-8'))

#
def update_log(action, pkt_type, seq, ack, size):
    # clocking time
    curr_time1 = time.time()	 # temp timer
    curr_time1 = curr_time1 * 1000 # convert to MS
    curr_time2 = curr_time1 - 1628191719295
    curr_time = str(format(curr_time2, '.2f')); seq = str(seq); size = str(size); ack = str(ack)
    # init arrays of args and col lens
    col_lens = [5, 12, 4, 10, 5, 3]

    args = [action, curr_time, pkt_type, seq, size, ack]
    # build string
    final_str = ""
    counter = 0
    # loop through columns
    for c in col_lens:
        arg_len = len(args[counter])
        #space_len = c - arg_len
        # add whitespace for each column
        space_str = " "*(c - arg_len) 
        # append each col to line
        final_str += str(args[counter]) + space_str
        counter += 1
    # add newline to final str
    final_str += "\n"
    if (DEBUG2):
        print(final_str)
    # append complete line to log
    
    Reciever_log.write(final_str)

    return curr_time1

# Erase and rewrite log file
open('Receiver_log.txt', 'w').close()
Reciever_log = open("Receiver_log.txt", "a+")


# Erase the file
open(sys.argv[2], 'w').close()

# Open FileReceived file
file = open(sys.argv[2], 'w')


# Intital the conter variables
Data_Received = 0
Data_Segments = 0
Duplicate_segments = 0


# Keeps connection open as long as program is running
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

sock.bind(server_address)
try:
    while True:
        if (DEBUG2):
            print("new cycle")
        
        # recieve data
        data = ""
        if (DEBUG2):
            print("recieve data")
        data, client_address = sock.recvfrom(4096)
        data = data.decode()
        if (DEBUG2):
            print("recieve data end")

        # Save received data and ip-address in list
        header = bits_to_header(data)
        body = get_body_from_data(data)
        message_size = utf8len(body)

        save_header['seq_num'] = header.seq_num
        save_header['ack_num'] = header.ack_num
        save_header['ack_bit'] = header.ack_bit
        save_header['syn'] = header.syn
        save_header['fin'] = header.fin
        
        # Checks if incoming data follows protocol
        if successful_connection == False :
            if header.syn == 1 \
                and header.ack_bit == 0:
                
                # update log for handshake stage 1
                update_log("rcv", 'S', header.seq_num, header.ack_num, message_size)
                
                # Save current recieved ack number
                last_recieve_ack = header.ack_num
                # Send data
                send_message = Header(0, (header.seq_num+1), ack_bit = 1, syn = 1, fin =0, data_size = 0, judge_timeout = header.judge_timeout)
                # Save current resend data
                #last_send_ack = header.ack_num
                sock.sendto(send_message.bits(), client_address)
                
                update_log("snd", 'SA', send_message.seq_num, send_message.ack_num, 0)
                
                # The first part of the handshake is completed so boolean is set to true
                firstpartofhandshakecompleted = True

            elif header.syn == 0 \
                    and header.ack_bit == 1 \
                    and firstpartofhandshakecompleted == True\
                    and firstpartofterminationcompleted == False:

                # Prints data and sets connection to true
                if (DEBUG2):
                    print('[CLIENT]: ' + body + ' from: ' + client_address[0])
                
                # update log for handshake stage 2
                update_log("rcv", 'A', header.seq_num, header.ack_num, message_size)
                    
                successful_connection = True
                message_number = 0
                #last_recieve_ack = header.ack_num
                #logger()
            elif header.ack_bit == 1\
                and header.fin == 1\
                and firstpartofterminationcompleted == True:
                # Last reciev ack for server close
                #sock.close()
                if (DEBUG2):
                    print('server closes1')
                
                # update log for recieve FIN
                update_log("rcv", 'A', header.seq_num, header.ack_num, 0)
                
                break
            
            
        # When protocol is followed, the client will be able to communicate with server
        elif successful_connection :
            if (DEBUG):
                print("Recieve message")
                print("message size?", message_size)
            if header.syn == 0\
                and header.fin == 0\
                and header.ack_bit == 0:
                # Prints data from client
                if (DEBUG):
                    print('successful_connection  recieve data: ' + body)
                
                
                # update log for recieve normal segments
                update_log("rcv", 'D', header.seq_num, header.ack_num, message_size)
                
                # Sets message number by adding one to the received number
                # Parsed to an int to make it possible to add one
                
                # For debugging print
                if (DEBUG):
                    print("last_send_ack: ", last_send_ack)
                    print("recieved seq_num: ", header.seq_num)

                # if repeat seq recived, drop it
                if (header.seq_num in acked_seq) or (header.seq_num in recieve_buffer.keys()):
                    Duplicate_segments += 1
                    continue

                if last_send_ack == header.seq_num:
                    # For acking seq in buffer
                    if (judge_lost == True) and recieve_buffer:
                        
                        # write current seq into file
                        #file.write(body)
                        # Add current seq into buffer
                        if header.seq_num not in recieve_buffer.keys():
                            recieve_buffer[header.seq_num] = body
                        
                        still_lost = False
                        #last_send_ack = header.seq_num
                        if (DEBUG):
                            print("before recieve_buffer.keys: ", recieve_buffer.keys())
                        for i in  sorted (recieve_buffer.keys()):
                            if i != last_send_ack:
                                still_lost = True
                                break
                            
                            seg_length = len(recieve_buffer[i])
                            file.write(recieve_buffer[i])
                            Data_Segments += 1
                            Data_Received += seg_length
                            acked_seq.append(i)
                            last_send_ack = i + seg_length
                            
                            # Make a new header
                            #if header.seq_num == i:
                            #    new_judge_timeout = header.judge_timeout
                            #else:
                            #    new_judge_timeout = 0
                            new_judge_timeout = header.judge_timeout
                            send_header = Header(seq_num = 1, ack_num = last_send_ack, ack_bit = 0, syn = 0, fin = 0, data_size = len(recieve_buffer[i]), judge_timeout = new_judge_timeout)
                        
                            # Sends the same response to the client no matter what is received
                            message = send_header.bits()
                            sent = sock.sendto(message, client_address)
                            
                            # update log for response ack message
                            update_log("snd", 'A', send_header.seq_num, send_header.ack_num, 0)
                            
                            recieve_buffer.pop(i, None)
                        if (DEBUG):
                            print("after recieve_buffer.keys: ", recieve_buffer.keys())
                        if still_lost == False:
                            judge_lost = False

                        else:
                            judge_lost = True

                    else:
                        # Normally recived 
                        last_recieve_ack = header.ack_num
                        file.write(body)
                        Data_Segments += 1
                        Data_Received += message_size
                        # Save seq recieved into acked_seq
                        acked_seq.append(header.seq_num)

                        # Whatever, just send below header
                        send_header = Header(header.ack_num, (header.seq_num+message_size), ack_bit = 0, syn = 0, fin = 0, data_size = message_size, judge_timeout = header.judge_timeout)
                        
                    
                     
                else:
                    # lost current packet
                    if (DEBUG2):
                        print("lost current packet")
                    if header.seq_num not in recieve_buffer.keys():
                        recieve_buffer[header.seq_num] = body
                    judge_lost = True
                    # Make a new header
                    send_header = Header(header.ack_num, last_send_ack, ack_bit = 0, syn = 0, fin = 0, data_size = message_size, judge_timeout = header.judge_timeout)
               
                # Sends the same response to the client no matter what is received
                last_send_ack = send_header.ack_num
                message = send_header.bits()
                sent = sock.sendto(message, client_address)

                # update log for response ack message
                update_log("snd", 'A', send_header.seq_num, send_header.ack_num, 0)
                
            elif header.fin == 1\
                and header.ack_bit == 0:
                # update log for FIN recieving
                update_log("rcv", 'F', header.seq_num, header.ack_num, 0)
                
                send_header = Header(header.ack_num, header.seq_num + 1, ack_bit = 1, syn = 0, fin = 1, data_size = 0, judge_timeout = header.judge_timeout)
                message = send_header.bits()
                sent = sock.sendto(message, client_address)
                
                # update log for FIN response
                update_log("snd", 'FA', send_header.seq_num, send_header.ack_num, 0)
                            
                if (DEBUG2):
                    print('[SERVER]: server prepares to close')
                    print("send_header seq: ", send_header.seq_num)
                    print("send_header fin: ", send_header.fin)
                successful_connection = False
                firstpartofterminationcompleted = True
            
                
            
finally:
    sock.close()
    file.close()
    #print('[SERVER]: server closes2')
    Reciever_log.write(("Amount of (original) Data Received (in bytes) - do not include retransmitted data: " + str(Data_Received) + "\n"))
    Reciever_log.write("Number of (original) Data Segments Received: " + str(Data_Segments) + "\n")
    Reciever_log.write("Number of duplicate segments received (if any): " + str(Duplicate_segments) + "\n")

    Reciever_log.close()
    



