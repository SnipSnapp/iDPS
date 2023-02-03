from scapy.all import *
from scapy.layers import http
from random import randrange
from random import randbytes
from ipaddress import IPv4Network, IPv4Address
from time import sleep
import string
import subprocess
#Doesn't quite need to be a class, but I don't feel comfortable not leaving as a function.
import re
import base64
IP_CIDR_RE = re.compile(r'(?<!\d\.)(?<!\d)(?:\d{1,3}\.){3}\d{1,3}\/\d{1,2}(?!\d|(?:\.\d))')
HEX_IDENTIFIER = re.compile(r'\|([0-9a-fA-F]{2} {0,1}){1,}\|')
BLACKLIST_IPS = []
BLACKLIST_PORTS = []
KNOWN_SERVICES= ['pop3','http']
CONTENT_MODIFIERS = ['depth:','offset:','distance:','within:','isdataat:','pcre:']
SUPPORTED_NEXT = ['base64_decode:','base64_data']
TEMP_BAD = ''
BAD_HEXSTRINGS = []
BLACKLIST_MACS = []
#these are separate because the list is different, and corresponds to http
HTTP_OPTS = ['http_cookie','http_header','http_uri','http_raw_cookie','http_raw_header','http_raw_uri','http_stat_code','uricontent','urilen','http_method']
#yes, technically it should have /,= but these will make snort stop processing, and an '==' is added to the end.
#yes it should technically have '+' but this causes a payload length issue because it makes x64 decode to unicode and not ascii which makes detections a little inconsistent.
x64_RANDOM_CHAR_LIST='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890+'
#PCRE IS BASIC NEEDS WORK
#NEED TO REFORMAT DATA FOR ISDATAAT

with open('Snort/config/blacklist_ips.txt', 'r') as f:
        BLACKLIST_IPS = f.readlines()
        f.close

for i,ele in enumerate(BLACKLIST_IPS):
    BLACKLIST_IPS[i] = ele.strip()

with open('Snort/config/blacklist_ports.txt','r') as f:
    BLACKLIST_PORTS = f.readlines()
    f.close
for i,ele in enumerate(BLACKLIST_PORTS):
    BLACKLIST_PORTS[i] = int(ele.strip())
with open('Snort/config/blacklist_macs.txt', 'r') as f:
    BLACKLIST_MACS = f.readlines()
    f.close
for i,ele in enumerate(BLACKLIST_MACS):
    BLACKLIST_MACS[i] = ele.strip()

class traffic_player:
    with open('Snort/config/blacklist_ips.txt', 'r') as f:
        BLACKLIST_IPS = f.readlines()
        f.close

    for i,ele in enumerate(BLACKLIST_IPS):
        BLACKLIST_IPS[i] = ele.strip()

    with open('Snort/config/blacklist_ports.txt','r') as f:
        BLACKLIST_PORTS = f.readlines()
        f.close
    for i,ele in enumerate(BLACKLIST_PORTS):
        BLACKLIST_PORTS[i] = int(ele.strip())
    
    def __init__(self, header, contents, client_mac, server_mac):
        self.traffic_protocol = None
        self.client = None
        self.client_port = None
        self.server = None
        self.server_port = None
        self.payload_flow = None
        self.payload_service = None
        self.payload = None
        self.client_mac = client_mac
        self.server_mac = server_mac
        self.base64_encode_next_payload=False
        self.base64_encode_offset = 0
        self.base64_encode_num_bytes = 0
        self.isdataat = 0
        self.sticky_x64_decode = False
        self.http_modifiers= {}
        self.build_traffic(header,contents)
        

    def get_random_mac(self):
        global BLACKLIST_MACS
        choices='1234567890ABCDEF'
        rval = 'FF:FF:FF:FF:FF:FF'
        while  rval in BLACKLIST_MACS :
            rval = ''
            for x in range(0,6):
                rval +=random.choice(choices)
                rval +=random.choice(choices)
                rval +=':'
            rval = rval[:-1]
        return rval


    #------------------------------------------------------------------#
    def build_traffic(self,header,contents):
        #rule header build    
        self.traffic_protocol = header['protocol']
        
        self.client = str(self.get_ip_address(header['rule_ip_src']))#
        self.client_port = self.get_port(header['rule_src_p'])
        self.server = str(get_ip_address(header['rule_ip_dst']))
        self.server_port = self.get_port(header['rule_dst_p'])
        if self.client_mac is None or self.client_mac == 'RANDOM':
            self.client_mac = self.get_random_mac()
        if self.server_mac is None or self.server_mac == 'RANDOM':
            self.server_mac = self.get_random_mac()
        self.server_mac = '00:0C:29:BC:72:6F'
       
        
        #Rule contents build
        self.payload_flow = self.get_flow(contents)
        if self.payload_flow[0] =="from_server":
            placehold = self.client_port
            self.client_port = self.server_port
            self.server_port = placehold

        self.payload_service = self.get_service(contents)
        #REALLY don't need this.  Instead need to modify the get_payload & Payload_helper functions to add to our dictionary of HTTP opts.
        print(len(self.http_modifiers))
        
        self.payload = self.get_payload(contents)
        print(f"Service:{self.payload_service}")
        print(f"Protocol:{self.traffic_protocol}")
        print(f"{self.client_mac} AT {self.client}:{self.client_port} -> {self.server_mac} AT {self.server}:{self.server_port}")
        
        print(f"Flow:{self.payload_flow}")
        print("|--Payload--|")
        print(self.payload)
        
        print('|-----------|\n')
        

    def send_full_convo(self):
        #print("Sending")
        opts = [('SAckOK','')]
        #send(IP(src=self.client, dst=self.server, flags='DF')/TCP(sport=self.client_port,  flags='S',  dport=self.server_port,options=opts))
        #print("sent 1 I guess")
        client_IP_Layer = Ether(src=self.client_mac,dst=self.server_mac)/IP(src=self.client, dst=self.server)
        server_IP_Layer = Ether(src=self.server_mac,dst=self.client_mac)/IP(src=self.server,dst=self.client)

        client_Hello = client_IP_Layer/TCP(sport=self.client_port, dport=self.server_port,  flags='S',  options=opts)
        sendp(client_Hello, verbose=True)

        Server_SA = server_IP_Layer/TCP(sport=self.server_port,dport = self.client_port, flags='SA', seq=client_Hello.seq, ack=client_Hello.ack + 1,options = opts)
        sendp(Server_SA, verbose=True)

        client_A = client_IP_Layer/TCP(sport=self.client_port, dport=self.server_port, flags ='A', seq=Server_SA.seq + 1, ack=Server_SA.ack)
        sendp(client_A, verbose=True)
        serv_pload = None
        client_payload = None
        if self.payload_flow[0] == 'from_server':
            serv_pload = self.payload
            client_payload = bytearray(self.get_valid_random_bytes(randrange(1,len(self.payload))))
        else:
            serv_pload = bytearray(self.get_valid_random_bytes(randrange(1,len(self.payload))))
            client_payload = self.payload
        
        Server_payload = server_IP_Layer/TCP(sport = self.server_port, dport = self.client_port, flags='PA', seq = client_A.seq, ack = client_A.ack)/serv_pload
        sendp(Server_payload, verbose=True)
        
        Client_Resp_1 = client_IP_Layer/TCP(sport = self.client_port, dport = self.server_port, flags='PA', seq = Server_payload.seq, ack = len(Server_payload[Raw].load))/client_payload
        sendp(Client_Resp_1, verbose=True)


        client_A = client_IP_Layer/TCP(sport = self.client_port, dport = self.server_port, flags='A',seq = Server_payload.seq, ack= len(Server_payload[Raw].load))
        sendp(client_A, verbose=True)

        server_A = server_IP_Layer/TCP(sport = self.server_port, dport = self.client_port, flags='A', seq = Server_payload.seq, ack=len(Client_Resp_1[Raw].load))
        sendp(server_A, verbose=True)

        server_pre_fin_psh = server_IP_Layer/TCP(sport = self.server_port,dport = self.client_port, flags='FPA', seq = len(Server_payload[Raw].load) + 1, ack = len(Client_Resp_1[Raw].load) )/bytearray(self.get_valid_random_bytes(randrange(1,len(Client_Resp_1[Raw].load)+2)))
        sendp(server_pre_fin_psh, verbose=True)

        client_FA = client_IP_Layer/TCP(sport=self.client_port, dport=self.server_port, flags='FA', seq=len(Client_Resp_1[Raw].load)+ 1, ack=len(server_pre_fin_psh[Raw].load))
        sendp(client_FA, verbose=True)

        serv_fin_ack = server_IP_Layer/TCP(sport=self.server_port, dport=self.client_port, flags='A', seq=client_FA.ack, ack=client_FA.seq +1)
        sendp(serv_fin_ack, verbose=True)
        #send(serv_signoff)
    def send_udp_convo(self):
        opts = [('SAckOK','')]
        #send(IP(src=self.client, dst=self.server, flags='DF')/TCP(sport=self.client_port,  flags='S',  dport=self.server_port,options=opts))
        #print("sent 1 I guess")
        client_IP_Layer = Ether(src=self.client_mac,dst=self.server_mac)/IP(src=self.client, dst=self.server)
        server_IP_Layer = Ether(src=self.server_mac,dst=self.client_mac)/IP(src=self.server,dst=self.client)
        
        for i in range(10):
            sendp(client_IP_Layer/UDP(sport = self.client_port, dport=self.server_port)/self.payload)
            sendp(server_IP_Layer/UDP(sport = self.server_port, dport=self.client_port)/self.payload)
    def send_full_http(self):
        TLDs =''
        with open('Snort/config/TLDs.txt','r') as f:
            TLDs = f.readlines()
            f.close
        self.client_port = 8080
        UAs = ''
        with open('Snort/config/HTTP_Usr_Agts.txt','r') as f:
            UAs = f.readlines()
            f.close
        letters = string.ascii_lowercase
        
        host = ''.join(random.choice(letters) for i in range(random.randint(5,20))) + '.'+random.choice(TLDs).strip().lower()
        Usr_Agent = ''.join(random.choice(UAs))
        Usr_Agent = Usr_Agent.strip().strip(' ')
        Get_Accept = 'text/html,application/xhtml+xml,application/xml,;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=*0.9'
        Get_encode = 'gzip, deflate'
        
        opts = [('SAckOK','')]
        client_IP_Layer = Ether(src=self.client_mac,dst=self.server_mac)/IP(src=self.client, dst=self.server)
        server_IP_Layer = Ether(src=self.server_mac,dst=self.client_mac)/IP(src=self.server,dst=self.client)
        client_Hello = client_IP_Layer/TCP(sport=self.client_port, dport=self.server_port,  flags='S',  options=opts)
        sendp(client_Hello, verbose=True)

        Server_SA = server_IP_Layer/TCP(sport=self.server_port,dport = self.client_port, flags='SA', seq=client_Hello.seq, ack=client_Hello.ack + 1,options = opts)
        sendp(Server_SA, verbose=True)

        client_A = client_IP_Layer/TCP(sport=self.client_port, dport=self.server_port, flags ='A', seq=Server_SA.seq + 1, ack=Server_SA.ack)
        sendp(client_A)
        Server_init_http = client_IP_Layer/TCP(sport=self.client_port,dport = self.server_port, flags='PA', seq=client_Hello.seq, ack=client_Hello.ack + 1,options = opts)/http.HTTP()/http.HTTPRequest(Method='GET', Host=host, User_Agent=Usr_Agent,Accept=Get_Accept, Connection='Keep-Alive')
        sendp(Server_init_http)
        
        Server_resp_init = server_IP_Layer/TCP(sport=self.server_port,dport=self.client_port, flags='PA', seq=Server_init_http.seq, ack= Server_init_http.ack)
        sendp(Server_resp_init)
        Server_Send_HTML=server_IP_Layer/TCP(sport=self.server_port,dport=self.client_port,flags='PA', seq=Server_init_http.seq,ack=Server_resp_init.ack)/http.HTTP()/http.HTTPResponse(Server=self.server, Location=host+self.http_modifiers.get('URI'))/'<html><p>Hello</p></html>'/http.http
        sendp(Server_Send_HTML)
        print(self.http_modifiers)
        
        exit(0)
    def send_traffic(self):
        #print(self.payload_flow[1])
        if self.traffic_protocol == 'tcp':
            if self.payload_service in 'http' or len(self.http_modifiers) !=0:
                #self.send_full_http()
                pass
            else:
                self.send_full_convo()
        elif self.traffic_protocol =='udp':
            self.send_udp_convo()
        
#Potential for infinite loops below function.  Future: Get rid of by checking the src. IP ranges and only finding IP addresses for randomization outside.
#Also Need to include RFC 1918 addresses for random IP addresses for local IPs for hosts.
    def get_ip_address(self,hostname):
        global TEMP_BAD
        my_ip = None
        if str(hostname).startswith('!'):
            TEMP_BAD = hostname[1:]
            if TEMP_BAD not in BLACKLIST_IPS:
                BLACKLIST_IPS.append(TEMP_BAD)
            else:
                TEMP_BAD = None
            hostname = 'any'

        if hostname == 'any':
            while my_ip is None:
                my_ip = f'{randrange(1,255)}.{randrange(1,255)}.{randrange(1,255)}.{randrange(1,255)}'
                if self.check_blacklist_ip(my_ip):
                    my_ip = None
        elif IP_CIDR_RE.match(hostname):
            ip_block = IPv4Network(hostname)
            my_ip = str(ip_block[randrange(0,ip_block.num_addresses- 3)])
            
            if self.check_blacklist_ip(hostname):
                print(f'Blacklisted IPv4 network found: {hostname}')
                my_ip = None    
        else:
            try:
                IPv4Address(hostname)
                my_ip = hostname
                if self.check_blacklist_ip(my_ip):
                    print(f'Blacklisted IPv4 address specified: {my_ip}')
                    my_ip = None

            except ValueError:
                print(f'Invalid IPv4 address specified: {hostname}')
        if len(TEMP_BAD) > 0:
            BLACKLIST_IPS.remove(TEMP_BAD)
            TEMP_BAD = None
        return my_ip

    def check_blacklist_ip(self,my_ip):
        bad = False
        if IP_CIDR_RE.match(my_ip):
            
            ipv4_network_spec = IPv4Network(my_ip)
            for bad_ip in BLACKLIST_IPS:
                bad_network = IPv4Network(bad_ip)
                if ipv4_network_spec.subnet_of(bad_network) or bad_network.subnet_of(ipv4_network_spec):
                    bad = True
        else:            
            for bad_ip in BLACKLIST_IPS:
                ipv4_network_spec = IPv4Network(bad_ip)
                if IP_CIDR_RE.match(bad_ip):
                    if IPv4Address(my_ip) in ipv4_network_spec:
                        bad=True
                        break
                else:
                    if my_ip == bad_ip:
                        bad=True
        return bad

    def get_port(self,port):
        my_port = 0
        if str(port).startswith('!'):
            port = port[1:]
            my_port = randrange(1,65535)
        if type(port) is list:
            for cnt,port_obj in enumerate(port):
                port[cnt] = self.get_port(port_obj)
            return random.choice(port)
        
        if port is None or str(port) == 'any':
            my_port = randrange(1,65535)
            while my_port in BLACKLIST_PORTS:
                my_port = randrange(1,65535)
        #SEEE https://www.sbarjatiya.com/notes_wiki/index.php/Configuring_snort_rules#Specifying_source_and_destination_ports
        elif '[' in str(port):
            print(port)
            port_def = port.strip('[').strip(']')
            port_def = port_def.split(',')
            start_p = self.get_port(port_def[0])
            end_p = start_p
            if len(port_def) > 1:
                end_p = self.get_port(port_def[1])
            port_rng = [start_p, end_p]
            my_port = random.choice(port_rng)
            return int(my_port)
                
        elif str(port).startswith(':'):
            my_port = randrange(1,int(port[1:]))
            
            while my_port in BLACKLIST_PORTS:
                my_port = randrange(1,int(port[1:]))
        elif str(port).endswith(':'):
            port = port.strip(':')
            #print(port)
            #TEMP NEEDS TO BE REWORKED.
            try:
                my_port =  randrange(int(port),65535)
            except:
                my_port = 1024
            while my_port in BLACKLIST_PORTS:
                my_port = randrange(int(port[:-1]),65535)
        elif ':' in str(port):
            nums = ''
            #TEMP.  NEEDS TO BE REWORKED.
            if ',' in port:
                nums = port.strip('[').strip(']').strip(':')
                nums = nums.split(',')
                print("Port range is:")
                print(nums)
            else:
                nums = str(port).strip('[').strip(']').split(':') 
            
              
            #print(nums)
            #print(port) 
           # print(nums[0])
            
            #print(nums[1])
            my_port =  randrange(int(nums[0]),int(nums[1]))
            while my_port in BLACKLIST_PORTS:
                my_port = randrange(int(nums[0]),int(nums[1]))
        else:
            return int(port)
        return my_port

    def get_flow(self,cont):
        flow = ''
        for x in cont:
            if x[0] == 'flow:':
                flow=x[1]
        payload_direction='from_client'
        payload_form = None
        if ',' in flow:
            parameters = flow.split(',')
            if parameters[0] in 'to_client' or parameters[0] in 'from_server':
                payload_direction = 'from_server'
            payload_form = parameters[1]
        else:
            if flow in 'to_client' or flow in 'from_server':
                payload_direction = 'from_server'
        return [payload_direction,payload_form]

    def set_next_content_opts(self,itemno):
        #print(itemno[0])
        #print(itemno)
        if 'base64_decode:'in itemno[0]:
            self.base64_encode_next_payload = True
            #print(itemno)
            the_x64data = itemno[1].split(',')
            for variablex64 in the_x64data:
                if 'offset' in variablex64:
                    self.base64_encode_offset = int(str(variablex64).replace('offset','').replace(' ',''))
                if 'bytes' in variablex64:
                    self.base64_encode_num_bytes = int(str(variablex64).replace('bytes','').replace(' ',''))
        if 'base64_data' == itemno[0]:
            #print("sticky-set")
            
            self.sticky_x64_decode = True
        #print("ENCODING WILL HAPPEN")
    def get_service(self,cont):
        svc = None
        for x in cont:
            
            if x[0] == 'metadata:service' or 'service' in x[0] or 'metadata:' in x[0]:
                if 'metadata' in x[0]:
                    meta = x[1].split(',')
                    for y in meta:
                        if 'service' in y:
                            k = y.split(' ')
                            print(k)
                            if k[0] =='':
                                svc=k[2]
                            else:
                                svc = k[1]
                            break
                else:
                    svc = x[1]
            
        print(svc)
        if svc in KNOWN_SERVICES  :
            return svc
        else:
            return "general"#KNOWN_SERVICES

    def get_payload(self,cont):
        payload = bytearray()
        #Find where we have content, if we do....
        x64_additions = []
        http_opt = None
        for count,details in enumerate(cont):
            if details[0] in SUPPORTED_NEXT:
                #print("My details are:")
                #print(details[1])
                #print(details)
                self.set_next_content_opts(details)
            elif details[0] == 'content:' or details[0] == 'pcre:':
                    #need helper option here, to append to string, we don't need a flag, We need to skip ahead in the enumeration until we reach what it is we seek. This needs to be done in an array.    
                #print(details)
                
                if not self.base64_encode_next_payload and not self.sticky_x64_decode:
                    curr_cap,count,http_opt=self.payload_helper(cont,count)
                    print(curr_cap,count,http_opt)
                    if http_opt is None and curr_cap is not None:
                        payload.extend(curr_cap)
                    elif curr_cap is not None:
                        self.http_modifiers.update({http_opt:bytearray(curr_cap)})
                    details = cont[count]
                else:
                    #print("DOING x64")
                    #print(details)

                    curr_cap,count,http_opt=self.payload_helper(cont,count)
                    curr_cap = base64.b64decode(curr_cap)
                    #print(curr_cap)
                    #I know this is really weird, but I did something I can't remember, and now this is the how we get x64 of the correct length. I know, super dumb, but it works? somehow?
                    #I'll fix it later, but this really is something I don't want to chase at the moment. It wasn't fun to figure out, granted I was playing overwatch & drinkin w/ some friends while coding it.
                    #After-all this is just a fun project that I have been doing.
                    if curr_cap is not None:
                        curr_cap = curr_cap.decode('utf-8')
                    if http_opt is not None:
                        self.http_modifiers.update({http_opt:curr_cap})
                    else:
                        x64_additions.append(curr_cap)
        #print(x64_additions)
        #I know I can do this in a better/faster way, but at the time this helped me troubleshoot.
        true_addition = bytearray()
        for x in x64_additions:
            addme = x
            if addme.endswith('=='):
                addme = addme[:-2]
            true_addition +=str(addme).encode('utf-8')
        print(true_addition)
        true_addition= base64.b64encode(true_addition)
        #print(true_addition)
        payload += true_addition[:-1] + self.get_valid_random_bytes(self.isdataat)
        return payload

    def get_valid_random_bytes(self,size):
        global x64_RANDOM_CHAR_LIST
        if self.sticky_x64_decode or self.base64_encode_next_payload:
            r_string = ''.join(random.choice(string.ascii_letters+string.digits)for i in range(size))
            r_string = r_string
            
            return base64.b64encode(r_string.encode('utf-8'))
        else:
            return randbytes(size)     
#currently doesn't support negative numbers in dist/offset
    def payload_helper(self,cont,count):
        not_flag = False
        print(f'{cont[count][0]} \t\t{cont[count][1]}')
        print(self.http_modifiers)
        if 'pcre' in cont[count][0] :
            print("WE DID PCRE EXITING")
            print(cont[count][1])
            return self.reverse_pcre(cont[count][1]),count+1,None
            
        if cont[count][1].startswith('!'):
            cont[count][1] = cont[count][1][1:]
            not_flag=True

        if str(cont[count][1]).startswith('\"') :
            cont[count][1] = cont[count][1][1:-1]
        build = bytearray()
        curr_loc = count 
        dofill=False
        if self.isdataat !=0:
            dofill=True
        orig = bytearray(self.get_content(cont[count][1]))    
        build.extend(orig)
        if not_flag:
            #print("reached_this")
            build = bytearray(self.get_valid_random_bytes(len(build)))
            
        curr_loc +=1
        paysize = 0
        offset = 0
        within = 0
        isdat =0
        #Need to check for banned hex strings.
        http_option = None
        if self.base64_encode_next_payload or self.sticky_x64_decode:
            #print("DECODING DATA")
            if self.base64_encode_num_bytes == 0:
                self.base64_encode_num_bytes = len(build)
            build = bytearray(build[:self.base64_encode_offset] + base64.b64encode(build[self.base64_encode_offset:self.base64_encode_offset+self.base64_encode_num_bytes]) + build[self.base64_encode_offset+self.base64_encode_num_bytes:])
            #if str(build.decode('utf-8')).endswith('=='):
            #    build = build[:-2]
            self.base64_encode_num_bytes = 0
            self.base64_encode_offset=0
            self.base64_encode_next_payload=False

            #print(build.decode('latin_1'))
        while curr_loc < len(cont) and (cont[curr_loc][0] in CONTENT_MODIFIERS or cont[curr_loc][0] in HTTP_OPTS) :
            print(f'{cont[curr_loc][0]} \t\t{cont[curr_loc][1]}')
            if 'depth:' == cont[curr_loc][0]:
                paysize += int(cont[curr_loc][1])
            elif 'within:' in cont[curr_loc][0]:
                within=  int(cont[curr_loc][1])
                #print(f'within: {within}')
            elif 'pcre:' in cont[curr_loc][0]:
                if build.decode('utf-8') in self.reverse_pcre(cont[curr_loc][1]).decode('utf-8'):
                    build = self.reverse_pcre(cont[curr_loc][1])
                else:
                    break
                #print(build)
                
            elif 'isdataat:' == cont[curr_loc][0]:
                if dofill== False:
                    self.isdataat = cont[curr_loc][1].split(',')
                    
                    self.isdataat = int(self.isdataat[0]) + 30
                else:
                    isdat = cont[curr_loc][1].split(',')
                    isdat = int(isdat[0])

            elif 'offset:' == cont[curr_loc][0] or 'distance:' == cont[curr_loc][0]:
                offset += int(cont[curr_loc][1])
            #THIS IS A BAD WAY OF DOING THIS

            else:
                for cnt,http_opt in enumerate(HTTP_OPTS):
                    print("THIS WAS HIT, WE KNOW THERE IS AN HTTP OPT HERE.")
                    if http_opt == cont[curr_loc][0]:
                        http_option = cont[curr_loc][0]
                break
            curr_loc +=1

        if offset > 0:
            build = bytearray(self.get_valid_random_bytes(offset)) + build
        if paysize > 0 :
            build.extend(self.get_valid_random_bytes(paysize))
        if self.isdataat> 0 and dofill:
            build.extend(bytearray(self.get_valid_random_bytes(self.isdataat)))                
            #self.isdataat = isdat
            
        if not_flag:
            exclude_me = bytearray(self.get_content(cont[count][1]))
            while exclude_me in build:
                #print("HEREee")
                #print(orig,end='\n\n')
                #print(build)
                build = build.replace(exclude_me,self.get_valid_random_bytes(len(exclude_me)))

        return build,curr_loc,http_option

    def get_content(self,le_string):
        print(le_string)
        
        content = le_string
        payload_content = bytearray()
        if content.startswith('\"') and content.endswith('\"'):
            content = content[1:-1]
        content = re.sub(HEX_IDENTIFIER,self.hex_match,content)
        payload_content.extend(content.encode('latin_1'))
        return payload_content

    def reverse_pcre(self,the_regex):

        print(os.getcwd())
        if the_regex.startswith('\"') and the_regex.endswith('\"'):
            the_regex = the_regex[1:-1]
        if the_regex.startswith('/^'):
            the_regex = the_regex[2:]
        re_opts = the_regex[the_regex.rfind('/'):]
        
        the_regex = the_regex[:the_regex.rfind('/')]
        #TODO IMPLEMENT SNORT OPTIONS.
        #print(re_opts)

        the_regex = self.rstring_arrbuilder(the_regex)
        with open('./Snort/pcre_gen.txt','w') as f:
            f.write(the_regex)
            f.close()
        result=subprocess.run([f'perl','.\\Snort\\reverse_pcre.pl', the_regex], shell=True, stdout=subprocess.PIPE)
        with open('./Snort/pcre_gen.txt','r') as f:
            the_regex = f.read()
            f.close()
        if 'D' in re_opts:
            if 'Cookie' in the_regex:
                self.http_modifiers.update({'http_cookie':bytearray(the_regex.encode('latin_1'))})
                return None
        if 'U' in re_opts:
            self.http_modifiers.update({'http_uri':bytearray(the_regex.encode('latin_1'))})
            return None
        return bytearray(the_regex.encode('latin_1'))
    def rstring_arrbuilder(self, the_regex):
        if '\s' in the_regex:
            the_regex = the_regex.replace('\\s',' ')
        matching_unsupported_negate = re.findall('\[\^.+\]',the_regex)
        print(matching_unsupported_negate)
        my_re = the_regex

        for x,negated in enumerate(matching_unsupported_negate):
            supported_characters = string.ascii_letters + string.digits
            replacement_string = negated[2:-1]
            if '\s' in negated:
                supported_characters = supported_characters.replace('\t','').replace('\n','').replace('\r','').replace('\x0b','').replace('\x0c','')
            if '\\n' in negated:
                supported_characters = supported_characters.replace('\\n','')
            for i in replacement_string:
                if i in supported_characters:
                    supported_characters = supported_characters.replace(i,'')
            my_re = my_re.replace(matching_unsupported_negate[x],'['+supported_characters.replace('[','\[').replace(']','\]').replace('+','\+').replace('-','\+').replace('>','').replace('<','').replace('\'','').replace('{','').replace('^','') +']') 

        return my_re

    def hex_match(self,the_match):
        match1 = the_match.group().strip('|')
        content = bytearray.fromhex(match1).decode('latin_1')
        
        return content




if __name__ == '__main__':
    header = {'rule_action': 'alert', 'protocol': 'tcp', 'rule_ip_src': 'any', 'rule_src_p': '110', 'rule_direction': '->', 'rule_ip_dst': 'any', 'rule_dst_p': 'any'}
    content = [['msg:', '"PROTOCOL-POP APOP USER overflow attempt"'], ['flow:', 'to_server,established'], ['content:', '"APOP"'], ['isdataat:', '256,relative'], ['pcre:', '"/^APOP\s+USER\s[^\\n]{256}/smi"'], ['metadata:', 'ruleset community, service pop3'], ['reference:', 'bugtraq,9794'], ['reference:', 'cve,2004-2375'], ['classtype:', 'attempted-admin'], ['sid:', '2409'], ['rev:', '11']]    
    ok = traffic_player(header,content,None, None)
    #ok.build_traffic(header,content)
    print("Build complete.")
    #ok.payload=bytearray('+OKSASLDIGEST-MD5+cmVhbG09Ig==K\x83\x15\x86\x04\x06\xe1\xb6\r8\xbc\xbb\xc22M\xa8\x92L\nB\xf1\xf78\xaa\x86\x16\xadEO\x92\x19\xbb\x9b\x9c4\x83\xa3\x8b\x1eINA\xf5\xbeN\xa1\xa5\x84\t|\xd5\xf6:<B\xc2#\xa3\x05\r\tj\xf6\xa2\xbc\xce*\xd1Iw\x9a\xc0\xff\xfe\x9d\x1db\x1e\xfa\xb0m\xc6\x89\xc6\x93W\\\x12[\xd5\xf6\xed\xad\xb9e\x04\x11\xe5b\xc5\xf4*\x03\xe7\xdf}\xc9}\x98\xb6\x12I\x1ek\x1aO\xd8\xebg\xe1\x8e\x13\xc7\x81thisisthestoryofagirlwhocriedariverthatdrownedthewholeworld'.encode('latin_1'))
   # print(len(ok.payload))
    #print(len('+OKSASLDIGEST-MD5+cmVhbG09Ig=='))
    print(ok.payload[154])
    #while True:
    for x in range(1):
        print('Sending')
        ok.send_traffic()
        sleep(5)
    #build_traffic(header, content)


