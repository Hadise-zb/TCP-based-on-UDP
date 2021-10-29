# My python version is 2.7.13 on VNC.
import socket, re, time, threading, random, sys

server_address = (sys.argv[1], int(sys.argv[2]))

save_header = {}
save_header['seq_num'] = 0
save_header['ack_num'] = 0
save_header['ack_bit'] = 0
save_header['syn'] = 0
save_header['fin'] = 0

t_lock=threading.Condition()

DEBUG = False
DEBUG2 = False

UPDATE_INTERVAL= 0.1
timeout=False

pdrop = float(sys.argv[7])
timeout_set = float(sys.argv[6])
seed = int(sys.argv[8])
MSS = int(sys.argv[5])
MWS = int(sys.argv[4])
max_packet = int(MWS / MSS)
message_size = MSS

sender_buffer = {}
sender_window = {}
seq_to_order = {}
send_list = []

message_amount = 0
seq_number = 0
socket_num = 0
last_send_time = 0

recieve_ack = 0
recieve_ack_count = 0
retransimit = False


data = None
server = None
splittedData = None
message_number = None
successful_connection = False
send_block = False
socketclose = False
timer_start = False

#sender_timeout = 0.5
timer_seq = 0


time_record = {}

random.seed(seed)


segments_sent = 0
packet_drop = 0
retransimit_seg = 0
duplicate_ack = 0

timer_control = True
sender_control = True

class Header:

    def __init__(self, seq_num, ack_num, ack_bit, syn, fin, data_size, judge_timeout):
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.ack_bit = ack_bit
        self.syn = syn
        self.fin = fin
        self.data_size = data_size
        self.judge_timeout = int(judge_timeout) 
        # judge_timeout is used to judge whether this segments is retransmit because of timeout or not
	
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
    bits = bits.decode()
    seq_num = int(bits[:32], 2)
    ack_num = int(bits[32:64], 2)
    ack_bit = int(bits[64], 2)
    syn = int(bits[65], 2)
    fin = int(bits[66], 2)
    data_size = int(bits[67:99], 2)
    judge_timeout = int(bits[99], 2)

    if (DEBUG2):
        print("seq num: ", seq_num)
        print("ack num: ", ack_num)
        print("ack bit: ", ack_bit)
        print("syn: ", syn)
        print("fin: ", fin)
        print("judge_timeout: ", judge_timeout)

    return Header(seq_num, ack_num, ack_bit, syn, fin, data_size, judge_timeout)

def get_body_from_data(data):
	data = data.decode()
	return data[100:]

def utf8len(s):
    return len(s)

def handle(seq, ack, pdrop, data, judge_timeout):
    global packet_drop
    
    data_size = len(data)
    random_num = random.random()
    if (DEBUG):
        print("random_num: ", random_num)
    
    if (random_num > pdrop):
        
        # send packet

        header = Header(seq, ack, ack_bit = 0, syn = 0, fin = 0, data_size = data_size, judge_timeout = int(judge_timeout))
        message = header.bits() + data
        if (DEBUG):
            print('In senddata : ', header.seq_num, header.ack_num)
        clientSocket.sendto(message, server_address)
        
        # set timer and update log file
        curr_time = update_log("snd", 'D', seq, ack, data_size)
        
    else:
        
        # drop packet
        if (DEBUG):
            print("drop this packet")
        curr_time = update_log("drop", 'D', seq, ack, data_size)
        packet_drop += 1
        
    return curr_time

# Update Sender_log
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
        space_str = " "*(c - arg_len) 
        # append each col to line
        final_str += str(args[counter]) + space_str
        counter += 1
    # add newline to final str
    final_str += "\n"
    if (DEBUG2):
        print(final_str)
    # append complete line to log
    
    Sender_log.write(final_str)

    return curr_time1


def timerThread():
    global last_send_time
    global timer_start
    global sender_timeout
    global timeout
    global sender_window
    global save_header
    global send_list
    global time_record
    global retransimit_seg
    global timer_control
    if (DEBUG2):
        print("Checks timerthread")
    while (timer_control):
        with t_lock:
            if (timer_start == True):
                # print("Checks if it's sender_timeout seconds since last message was sent")
                # Checks if it's sender_timeout seconds since last message was sent
                if last_send_time + timeout_set <= (time.time() * 1000):
                    if (DEBUG2):
                        print("Timeout happen: ", last_send_time)
                        print("Timeout happen current time: ", (time.time() * 1000))
                    #timer_start = False
                    #timeout = True
                    if timer_seq in sender_window.keys():
                        last_send_time = handle(timer_seq, 1, pdrop, sender_window[timer_seq], 1)
                        time_record[timer_seq] = last_send_time
                        send_list.append(timer_seq)
                        timer_start = True
                        retransimit_seg += 1
                    else:
                        timer_start = False
                    #last_send_time = senddata(sender_window[timer_seq], timer_seq)
                    if (DEBUG2):
                        print("sender_window: ", sender_window.keys())
                    timeout = False
            t_lock.notify()
    


def receivedataThread():
    global t_lock
    #global clients
    global clientSocket
    #global serverSocket
    global successful_connection
    global message_number
    #global message_size
    global socketclose

    global recieve_ack
    global recieve_ack_count
    global retransimit
    global sender_window
    global socket_num
    global sender_buffer
    global seq_number
    global seq_to_order
    global send_list
    global time_record
    global last_send_time
    global timer_seq
    global timer_start
    global save_header
    global retransimit_seg
    global duplicate_ack
    
    if (DEBUG):
        print('client is ready for service')

    while (1):
        #print("successful_connection: ", successful_connection)
        
        if successful_connection:
            if (DEBUG):
                print("Receive data after three way handshake")
                # Receive data
                print("Receive data: ")
                print("socket_num: ", socket_num)
                print("message_amount: ", message_amount)
            if socket_num > message_amount:
                if (DEBUG2):
                    print("Jump out loop")
                    print("sender_window: ", sender_window.keys())
                if bool(sender_window) == False:
                    break
            
            data, server = clientSocket.recvfrom(4096)
            
            header = bits_to_header(data)
            body = get_body_from_data(data)
            message_size = utf8len(body)

            # Put update log under t_lock, avoid write confliction.
            update_log("rcv", 'A', header.seq_num, header.ack_num, message_size)    
            
            with t_lock:
                # Put update log under t_lock, avoid write confliction.
                # update_log("rcv", 'A', header.seq_num, header.ack_num, message_size)
                save_header['seq_num'] = header.seq_num
                save_header['ack_num'] = header.ack_num
                save_header['ack_bit'] = header.ack_bit
                save_header['syn'] = header.syn
                save_header['fin'] = header.fin

                #data = body
                
                #splittedData = re.split('[\s=-]', data)
                #splittedData.append(server[0])
                
                # Normally recieve data
                if header.syn == 0 and header.ack_bit == 0\
                    and header.fin == 0:
                    if header.ack_num == recieve_ack:
                        recieve_ack_count += 1
                        duplicate_ack += 1
                    else:
                        recieve_ack = header.ack_num
                        
                        # Use recievd ack to get acked_seq
                        acked_seq = header.ack_num - header.data_size
                        if (DEBUG2):
                            print("Deleting ack: ", header.ack_num)
                            print("Deleting seq: ", acked_seq)
                            print("Deleting size: ", header.data_size)
                        # Set timer to next unacked seq
                        if (DEBUG):
                            print("time_record: ", time_record)
                            print("recieve_ack: ", recieve_ack)
                        
                        # If , don't set timer
                        if socket_num > message_amount and len(sender_window.keys()) == 1 and (acked_seq in sender_window.keys()):
                            timer_start = False
                        else:
                    
                            if recieve_ack in time_record.keys():
                                if header.judge_timeout == 1:
                                    curr_time1 = time.time()	 # temp timer
                                    curr_time1 = curr_time1 * 1000
                                    timer_seq = recieve_ack
                                    last_send_time = curr_time1
                                    
                                    if (DEBUG2):
                                        print("recieve_ack: ", recieve_ack)
                                        print("last_send_time", last_send_time)
                                else:
                                    timer_seq = recieve_ack
                                    last_send_time = time_record[recieve_ack]
                                    
                                    if (DEBUG2):
                                        print("recieve_ack2: ", recieve_ack)
                                        print("last_send_time2", last_send_time)
                                
                            else:
                                timer_start = False

                        

                        # Add new seq to window
                        if acked_seq in sender_window:
                
                            if (DEBUG2):
                                print("value of socket_num: ", socket_num)
                            if socket_num > message_amount:
                                # Don't put new seq in window anymore, just remove acked seq from window
                                # Delete the acked sequence whatever it is in window or not
                                sender_window.pop(acked_seq, None)
                                if sender_window:
                                    # Still remain seq in window waitting for acked
                                    if (DEBUG2):
                                        print("sender_window is not empty: ", sender_window.keys())
                                    continue
                                else:
                                    break
                            else:
                                buffer_message_size = utf8len(sender_buffer[socket_num])
                                if (DEBUG):
                                    print("before adding message size: ", seq_number)
                                    
                                    print("seq_number after adding message size: ", seq_number)
                                sender_window[seq_number] = sender_buffer[socket_num]
                                seq_to_order[seq_number] = socket_num
                    
                                
                                # here can be swap to recieve_ack
                                # seq_number = recieve_ack
                                seq_number = seq_number + buffer_message_size
                                if (DEBUG):
                                    for n in sender_window:
                                        print("sender_window key: ", n)
                            socket_num += 1
                        
                        # Delete the acked sequence whatever it is in window or not
                        sender_window.pop(acked_seq, None)

                # Check fast retransmition
                if recieve_ack_count >= 3:
                    retransimit = True
                else:
                    retransimit = False
                
                # implement fast retransimit here
                if retransimit == True:
                    if header.ack_num in sender_window.keys():
                        if (DEBUG2):
                            print("Begin to fast retransmit")
                        timer_start = False
                        curr_time = handle(header.ack_num, header.ack_num, pdrop, sender_window[header.ack_num], 1)
                        
                        time_record[header.ack_num] = curr_time
                        # Set timer_seq before set curr_time
                        timer_seq = header.ack_num
                        last_send_time = curr_time
                        send_list.append(timer_seq)
                        timer_start = True
                        retransimit_seg += 1
                    # Set last seq number back to current seq rather than next
                    #seq_number = seq_number - message_size
                    retransimit = False
                    recieve_ack_count = 0
                   

                #Termination start
                if (header.fin == 1) \
                    and (header.ack_bit == 1):
                    #and header.address == server[0]:   # make sure the server address
                    
                    message = Header(header.ack_num, (header.seq_num+1), ack_bit = 1, syn = 0, fin = 1, data_size = 0, judge_timeout = 0)
                    clientSocket.sendto(message.bits(), server_address)
                    if (DEBUG):
                        print("close client", server_address[0])
                        print('closing socket')
                    break
                #notify the thread waiting
                t_lock.notify()
            

    if  socketclose == False:
        if fourwaystermination() == True:
            socketclose = True
            clientSocket.close()

def senddataThread():
    global t_lock
    global clientSocket
    global timeout
    global message_number
    global successful_connection
    #global message_size
    global seq_number
    global retransimit 
    global message_amount
    global max_packet
    global sender_window
    global socket_num
    global socketclose

    global seq_to_order
    global recieve_ack_count
    global send_list

    global time_record
    global last_send_time
    global timer_seq
    global timer_start
    global save_header

    message_number, successful_connection = threewayhandshake()
    if successful_connection:
        if (DEBUG):
            print("Begin to send data")
        # Initial the Window buffer
        socket_num = 0        
        for i in range(max_packet):
            message_size = utf8len(sender_buffer[socket_num])
            
            seq_to_order[seq_number] = socket_num
            sender_window[seq_number] = sender_buffer[socket_num]
            seq_number = seq_number + message_size

            socket_num += 1


        # This list used to store the seq number of already sent sequence
        last_send = 0
        while(sender_control):    
            i = 0
            for order in sorted (sender_window.keys()):
                with t_lock:
                    if order not in send_list:
                        if (DEBUG):
                            print("beign send new message")
              
                        curr_time = senddata(sender_window[order], order)
                        
                        time_record[order] = curr_time

                        if seq_to_order[order] == 0 or timer_start == False:
                            timer_seq = order
                            #timer(curr_time, "set")
                            last_send_time = curr_time
                            timer_start = True
                            if (DEBUG2):
                                print("timer start")
                        
                        # put sent seq in list 
                        send_list.append(order)

                        #already_send.append(int(seq_to_order[sender_window[order]]))
                        if (DEBUG):
                            print("last send order:", order)
                            print("seq_to_order: ", seq_to_order)
                            print("last_send: ", seq_to_order[order])
                        last_send = seq_to_order[order]
                        if (DEBUG):
                            print("send new message done")
                        i += 1
                    #notify other thread
                    t_lock.notify()
            #sleep for UPDATE_INTERVAL
            #time.sleep(UPDATE_INTERVAL)
    

def fourwaystermination():
    global sender_control
    
    fin_header = Header(save_header['ack_num'], save_header['seq_num'], ack_bit = 0, syn = 0, fin = 1, data_size = 0, judge_timeout = 0)
    message = fin_header.bits()
    clientSocket.sendto(message, server_address)
    update_log("snd", 'F', save_header['ack_num'], save_header['seq_num'], size = 0)
    if (DEBUG):
        print("client prepare to terminate")
    while (1):
        # Receive termination message
        data, server = clientSocket.recvfrom(4096)
        header = bits_to_header(data)  
          
        if (DEBUG2):
            print("last recieve")
        

        if (header.ack_bit == 1) \
            and (header.ack_num == (fin_header.seq_num + 1))\
            and (header.fin == 1):

            # update log for recieving ack for FIN
            update_log("rcv", 'FA', header.seq_num, header.ack_num, size = 0)

            # Debugging print:
            if (DEBUG):
                print("Last send")
            # Last send
            fin_header = Header(header.ack_num, header.seq_num + 1, ack_bit = 1, syn = 0, fin = 1, data_size = 0, judge_timeout = 0)
            message = fin_header.bits()
            clientSocket.sendto(message, server_address)
            update_log("snd", 'A', fin_header.seq_num, fin_header.ack_num, size = 0)
            sender_control = False
            return True
    return False


def threewayhandshake():
    global seq_number

    message_number_2 = '0'
    successful_connection_2 = False

    # Starts three-way handshake
    seq_num = 0
    syn_header = Header(seq_num, 0, ack_bit = 0, syn = 1, fin = 0, data_size = 0, judge_timeout = 0)
    clientSocket.sendto(syn_header.bits(), server_address)
    
    # Update log for handshake
    update_log("snd", 'S', syn_header.seq_num, syn_header.ack_num, 0)

    # Receive data
    data, server = clientSocket.recvfrom(4096)
    header = bits_to_header(data)

    # Remenber to check lec note for making sure
    save_header['seq_num'] = header.seq_num + 1
    save_header['ack_num'] = header.ack_num
    save_header['ack_bit'] = header.ack_bit
    save_header['syn'] = header.syn
    save_header['fin'] = header.fin
    
    if (DEBUG):
        print("ack_num: {}", header.ack_num)
        print("syn: {}", header.syn)


    if (header.syn == 1) \
        and (header.ack_num == (syn_header.seq_num + 1)):
        
        #and header.address == server[0]:   # make sure the server address
        update_log("rcv", 'SA', header.seq_num, header.ack_num, 0)

        message = Header(header.ack_num, (header.seq_num+1), ack_bit = header.ack_bit, syn = 0, fin = 0, data_size = 0, judge_timeout = 0)
        
        # Update seq_number to current sending sequence number
        seq_number = header.ack_num

        clientSocket.sendto(message.bits(), server_address)
        update_log("snd", 'A', message.seq_num, message.ack_num, 0)
        successful_connection_2 = True
        if (DEBUG):
            print("[CLIENT]: Connected successfully to server", server_address[0])

    return message_number_2, successful_connection_2


def senddata(data, seq):
    # Delay to make sure the server has time to respond before client sends a new package
    #time.sleep(0.1)

    if successful_connection:
        # Message is sent to server with the incremented message number
        # Take global seq as sending ack (Should be 1 in current case)
        '''
        header = Header(seq, save_header['seq_num'], ack_bit = 0, syn = 0, fin = 0, data_size = 0)
        message = header.bits() + data
        print('In senddata : ', header.seq_num, header.ack_num)
        clientSocket.sendto(message, server_address)
        '''
        curr_time = handle(seq, save_header['seq_num'], pdrop, data, 0)
    elif successful_connection is False:
        if (DEBUG):
            print("Couldn't send data. Successful connection to server isn't established")
        curr_time = 0
    return curr_time


clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

open('Sender_log.txt', 'w').close()
Sender_log = open("Sender_log.txt", "a+")

file = open(sys.argv[3], "rb")
file_size = 0
byte = file.read(MSS)
while byte:
    sender_buffer[message_amount] = byte
    message_amount += 1
    file_size += len(byte)
    byte = file.read(MSS)
message_amount -= 1
file.close()


try:
    timer_thread=threading.Thread(name="TimerHandler",target=timerThread)
    timer_thread.daemon=True
    timer_thread.start()

    recv_thread=threading.Thread(name="RecvHandler", target=receivedataThread)
    recv_thread.daemon=True
    recv_thread.start()

    send_thread=threading.Thread(name="SendHandler",target=senddataThread)
    send_thread.daemon=True
    send_thread.start()
    

    #this is the main thread
    while True:
        if socketclose == True:
            timer_control = False
            timer_thread.join()
            #print("timer thread end")
            recv_thread.join()
            #print("recv thread end")
            sender_control = False
            send_thread.join()
            #print("send thread end")
            break
       
             

finally:
    #print('closing socket')
    clientSocket.close()
    Sender_log.write(("Amount of (original) Data Transferred (in bytes): " + str(file_size) + "\n"))
    Sender_log.write("Number of Data Segments Sent (excluding retransmissions): " + str(message_amount+1) + "\n")
    Sender_log.write("Number of (all) Packets Dropped (by the PL module): " + str(packet_drop) + "\n")
    Sender_log.write("Number of Retransmitted Segments: " + str(retransimit_seg) + "\n")
    Sender_log.write("Number of Duplicate Acknowledgements received: " + str(duplicate_ack) + "\n")
    Sender_log.close()
    
    

