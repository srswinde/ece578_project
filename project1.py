#!/usr/bin/python3

from threading import Thread, Lock
from queue import Queue, Empty
import time
import random
import math
from counters import count_down, Counter
import copy
import sys
import uuid
import json
import xlsxwriter

# time in micro seconds
SLOT = 20
SIFS = 20
DIFS = 40



# data size in bytes
FRAME = 1500
RTS = 30
CTS = 30
ACK = 30

TX_RATE = 6e6 #mbs
DATA_TX_TIME = FRAME*8/TX_RATE

CW = 4
CW_MAX = 1024

MAX_COUNT = 5000

FRAME_TX_TIME = FRAME

 


class Station:
    """Simulates the nodes of the wireless network"""

    def __init__(self, medium, name, tosend_frames, virtual_sense=False):
        self.medium = medium
        self.name = name
        self.receiver = Queue()
        self.backoff_countdown = count_down( top=None, name="{} Back Off".format(self.__repr__()) )
        self.medium.counter.register( self.backoff_countdown )
        self.backoff_multiplier = 1
        self.sent_frame = None
        self.tosend_frames = tosend_frames
        self.received_frames = []
        self.ack = None
        self.success_count = 0
        self.collision_count = 0
        self.virtual_sense = virtual_sense
        self.sentRTS = None
        with open("{}_frames.dat".format(self.name), "w") as fd:
            for frame in tosend_frames:
                fd.write( "{:f} 1\n".format(frame.slot) )

        if not virtual_sense:
            self.clear_to_send = True
        





    def one_loop( self ):
        """This is what we do every iteration
        of the count."""
        if self.backoff_countdown:
            if not self.medium.isIdle():
                self.backoff_countdown.freeze()


        try:
            #did we recv data?
            data = self.receiver.get(block=False)
        except Empty:
            #... nope we didn't
            data = None

        if data:
            #We have data
            if data == Collision:
                self.collision_count+=1
                
            if data.receiver == self.name:

                #data is for us
                if data == Frame:

                    self.received_frames.append(data)
                    if not self.virtual_sense:
                        self.medium.SIFS_countdown.start(SIFS, self.medium.put, Ack(data) )
                    else:
                        self.medium.DIFS_countdown.start( DIFS, self.medium.DIFS_finish )
                        self.backoff_multiplier=1


                
                elif data == Ack:
                    #Data is an Ack we know our Frame was recvd
                    if data == self.sent_frame:
                        self.sent_frame = None
                        self.success_count+=1
                        self.backoff_multiplier = 1


                    self.medium.DIFS_countdown.start(DIFS, self.medium.DIFS_finish )
                elif data == RTS:
                    if data.sender is not self.name:

                        self.sentCTS = CTS( data )
                        self.medium.SIFS_countdown.start( SIFS, self.medium.put, self.sentCTS )

                elif data == CTS:

                    if self.sentRTS:
                        if self.sentRTS == data:
                            self.medium.SIFS_countdown.start( SIFS, self.send )
                            self.success_count+=1

                        self.backoff_countdown.freeze()





            elif data == Collision:
                #Collision our data was not sent. 
                if self.sent_frame is None:
                    #self.collision_count+=1
                    self.backoff_multiplier+=1




    def send ( self ):
        if self.medium.isIdle() or self.clear_to_send:
            self.sent_frame = self.tosend_frames.pop(0)

            self.medium.put( self.sent_frame )


    def __repr__( self ):
        return "Sation {}".format( self.name )

    def DIFS_finish( self ):
        if not self.virtual_sense:
            self.backoff_countdown.unfreeze()
            if self.sent_frame:
                self.sent_frame = None

            if len( self.tosend_frames ) > 0:
            #do we have a frame?
                if self.medium.counter.count > self.tosend_frames[0].slot:
                #Is it time to send the frame?

                    backoff = random.randint( 0, CW*self.backoff_multiplier )*SLOT
                    if self.backoff_countdown:
                        self.backoff_countdown.unfreeze()
                    else:
                        self.backoff_countdown.start( top=backoff, fxn=self.send )


        else:#virtual sense

            if len( self.tosend_frames ) > 0:
                # we have frames to send

                if self.medium.counter.count > self.tosend_frames[0].slot:
                    #they have arrived

                    self.backoff_countdown.unfreeze()
                    if self.backoff_countdown:
                        pass
                    
                    else:
                        backoff = random.randint( 0, CW*self.backoff_multiplier )*SLOT
                        self.sentRTS = RTS(self.name, "B")
                        self.backoff_countdown.start( backoff, self.medium.put, self.sentRTS )









class Connection(Queue):
    """Connection class inherits from queue.
    Here we can overwrite the methods
    put and get. this will give us access
    to the receiving and transmitting. 

    This class simulates the shared medium 
    and starts the countdown for the 
    a packet to share the medium. 
    """


    def __init__( self, counter ):
        self.counter = counter

        self.SIFS_countdown = count_down( top=None, name="SIFS", trigger_function = self.SIFS_finish )
        self.DIFS_countdown = count_down( top=None, name="DIFS", trigger_function = self.DIFS_finish )
        self.inTransit = None
        self.traverse_countdown = count_down(top=None, name="traverse", trigger_function=self.tx_arrive)
        self.DIFS_countdown.start(DIFS, self.DIFS_finish )

        self.secret_queue = Queue()
        self.counter.register( self.traverse_countdown )
        self.counter.register( self.SIFS_countdown )
        self.counter.register( self.DIFS_countdown )
        self.outfile = open("Connection.dat", 'w')

        super().__init__()



    def get( self, *args, **kwargs ):
        """"""

        if not self.secret_queue.empty():
            #A transmission has arrived
            data = self.secret_queue.get()
            """
            if data == Ack:
                self.DIFS_countdown.start( top=DIFS )

            elif data == Frame:
                self.SIFS_countdown.start( top=SIFS )
            """ 

            for station in stations:
                station.receiver.put( data )

            if data == Collision:
                self.SIFS_countdown.start( SIFS, self.wait_for_ack, Ack(data).size )


        try:
            data = super().get( *args, **kwargs )
        except Empty:
            data = None

        if self.DIFS_countdown:
            self.inTransit = None

        elif self.SIFS_countdown:
            self.inTransit = None

        if data:
            tx_time_s = data.size*8/TX_RATE 
            tx_time_microseconds = tx_time_s*1e6
            if self.isIdle():
                self.traverse_countdown.start( tx_time_microseconds, self.tx_arrive, data )

            else:
                #Collisison cancel the transmission
                self.traverse_countdown.cancel()
                if self.traverse_countdown >= tx_time_microseconds:
                    
                    tx_time_microseconds = self.traverse_countdown
                data = Collision()
                self.traverse_countdown.start( tx_time_microseconds, self.secret_queue.put, data )

            self.inTransit = data

        self.writestatus()
        return None
        

    def wait_for_ack( self, acksize ):
        tx_time_s = acksize*8/TX_RATE
        tx_time_microseconds = tx_time_s*1e6

        self.DIFS_countdown.start( tx_time_microseconds, self.DIFS_finish )
        
    def put( self, msg, *args, **kwargs ):
        super().put( msg, *args, **kwargs )

    def tx_arrive( self, data ):
        self.secret_queue.put( data )

    def collision_arrive( self ):
        self.secret_queue.put( Collision() )


    def isIdle( self ):

        if self.inDIFS():
            return False
        elif self.inSIFS():
            return False
        elif self.traverse_countdown:
            return False

        else:
            return True

    def DIFS_finish( self ):
        for station in stations:
            station.DIFS_finish()
        transmitting  = False
        for station in stations:
            for station in stations:
                if station.backoff_countdown:
                    transmitting = True

        if not transmitting:
            self.DIFS_countdown.start( DIFS, self.DIFS_finish )
        


    def SIFS_finish( self ):
        print( "SIFS is over" )

    def inDIFS( self ):
        return bool( self.DIFS_countdown )

    def inSIFS( self ):
        return bool( self.SIFS_countdown )

    def writestatus(self):

        self.outfile.write("{:f} {:d} {:d} {:d}\n".format( self.counter.count, self.inDIFS(), self.inSIFS(), self.inTransit is not None) )



    
    def status( self ):
        outstr = ""
        if self.inDIFS():
            outstr+="DIFS "
        if  self.inSIFS():
            outstr+="SIFS "
        if self.isIdle():
            outstr+="Idle"
        if self.traverse_countdown:
            outstr+=self.traverse_countdown.__repr__()
        if self.inTransit:

            outstr+=str(self.inTransit)
        return outstr



class Transmission():
    """Place holder for anything that 
    is methods and members common to 
    acks and frames"""
    def __init__( self, sender, receiver, slot=None ):
        self.sender = sender # address or name of sender.
        self.receiver = receiver #address or name of receiver.
        self.slot = slot
        self.uuid = uuid.uuid4()

    def __repr__( self ):
        return "<TX sender: {} recver: {} tx_type:{} slot:{} uuid:{}>".format(self.sender, self.receiver, self.tx_type, self.slot, self.uuid)

    def __eq__( self, other ):
        if type(other) == type:
            if self.__class__ == other:
                return True
            else:
                return False
        else:
            if self.uuid == other.uuid:
                return True
            else:
                return False




class Collision( Transmission ):
    tx_type = "Collision"
    size = None
    uuid = None
    sender = None
    receiver = None
    slot=None

    def __init__( self ):
        pass


class Ack( Transmission ):
    tx_type = "Ack"
    size = 30
    slot=None

    def __init__(self, frame):
        if frame != Collision:
            self.sender = frame.receiver
            self.receiver = frame.sender
            self.uuid = frame.uuid
        else:
            self.send = None
            self.receiver = None

class Frame( Transmission ):
    tx_type = "Frame"
    size = 1500


class RTS( Transmission ):
    tx_type = "RTS"
    size = 30

class CTS( Transmission ):

    tx_type = "CTS"
    size = 30
    slot=None

    def __init__(self, rts):
        self.sender = rts.receiver
        self.receiver = rts.sender
        self.uuid = rts.uuid

def poisson_distribution( Lambda=1, simtime=10 ):
    X = []
    x=0

    dummy = 0

    while x < simtime:
        u = random.random() # random number between 0  and 1
        dummy =((-1/Lambda)*math.log(1-u))
        x+=dummy
        X.append(int(SLOT*round(x*1e6/SLOT)))
        
    return X





def run_sim_scenarioA_CSMA1(lambda_A, lambda_C ):
    """Run the simulation at different lambdas"""
    simtime = 10e6 # time in microsecond, 10 seconds

    #generate the Frames to be sent of the simulation
    a2b = [Frame("A", "B", slot) for slot in poisson_distribution(Lambda=lambda_A) ]
    c2d = [Frame("C", "D", slot) for slot in poisson_distribution(Lambda=lambda_C) ]
    
    #start the counter class
    counter = Counter(simtime*2)

    #Connection class simulates the shared medium. 
    conn = Connection(counter)

    #The stations connected to the shared medium.
    A = Station( conn , 'A', a2b, False )
    B = Station( conn , 'B', [], False )
    C = Station( conn , 'C', c2d, False )
    D = Station( conn , 'D', [], False )

    #make the stations global for convienience. 
    global stations
    stations = (A, B, C, D)

    #count up in micro seconds stop at 10 seconds. 
    for cnt in counter:
        if cnt > simtime:
            break
        
        data = conn.get( block=False )
        for station in stations:
            station.one_loop()
        """
        print( cnt )
        print( conn.inTransit )

        print( counter.status() )
        """
    for station in stations:

        print("{} success:{}, collisions:{} Throughput {}".format( station, 
            station.success_count, 
            station.collision_count,
            station.success_count*Frame.size*8/(simtime/1e6)) )

    return { 
                "A":A.success_count*Frame.size*8/(simtime/1e6), 
                "C": C.success_count*Frame.size*8/(simtime/1e6),
                "Throughput":(A.success_count+C.success_count)*Frame.size*8/(simtime/1e6),
                "Collisions": A.collision_count,
                "Fairness":float(A.success_count)/C.success_count
                }


def run_sim_scenarioA_CSMA2(lambda_A, lambda_C ):
    """Run the simulation at different lambdas"""
    simtime = 10e6 # time in microsecond, 10 seconds

    #generate the Frames to be sent of the simulation
    a2b = [Frame("A", "B", slot) for slot in poisson_distribution(Lambda=lambda_A) ]
    c2d = [Frame("C", "D", slot) for slot in poisson_distribution(Lambda=lambda_C) ]
    
    #start the counter class
    counter = Counter(simtime*2)

    #Connection class simulates the shared medium. 
    conn = Connection(counter)

    #The stations connected to the shared medium.
    A = Station( conn , 'A', a2b, True )
    B = Station( conn , 'B', [], True )
    C = Station( conn , 'C', c2d, True )
    D = Station( conn , 'D', [], True )

    #make the stations global for convienience. 
    global stations
    stations = (A, B, C, D)

    #count up in micro seconds stop at 10 seconds. 
    for cnt in counter:
        if cnt > simtime:
            break
        
        data = conn.get( block=False )
        for station in stations:
            station.one_loop()
        """
        print( cnt )
        print( conn.inTransit )

        print( counter.status() )
        """
    for station in stations:

        print("{} success:{}, collisions:{} Throughput {}".format( station, 
            station.success_count, 
            station.collision_count,
            station.success_count*Frame.size*8/(simtime/1e6)) )

    return { 
                "A":A.success_count*Frame.size*8/(simtime/1e6), 
                "C": C.success_count*Frame.size*8/(simtime/1e6),
                "Throughput":(A.success_count+C.success_count)*Frame.size*8/(simtime/1e6),
                "Collisions": A.collision_count,
                "Fairness":float(A.success_count)/C.success_count
                }


def run_sim_scenarioB_CSMA1(lambda_A, lambda_C ): 
    """Run the simulation at different lambdas"""
    simtime = 10e6 # time in microsecond, 10 seconds

    #generate the Frames to be sent of the simulation
    a2b = [Frame("A", "B", slot) for slot in poisson_distribution(Lambda=lambda_A) ]
    c2b = [Frame("C", "B", slot) for slot in poisson_distribution(Lambda=lambda_C) ]
    
    #start the counter class
    counter = Counter(1e10)

    #Connection class simulates the shared medium. 
    conn = Connection(counter)

    #The stations connected to the shared medium.
    A = Station( conn , 'A', a2b, False )
    B = Station( conn , 'B', [], False )
    C = Station( conn , 'C', c2b, False )

    #make the stations global for convienience. 
    global stations
    stations = (A, B, C)

    #count up in micro seconds stop at 10 seconds. 
    for cnt in counter:
        if cnt > simtime:
            break
        
        data = conn.get( block=False )
        for station in stations:
            station.one_loop()

    return { 
                "A":A.success_count*Frame.size*8/(simtime/1e6), 
                "C": C.success_count*Frame.size*8/(simtime/1e6),
                "Throughput":(A.success_count+C.success_count)*Frame.size*8/(simtime/1e6),
                "Collisions": A.collision_count,
                "Fairness":float(A.success_count)/C.success_count
                }



def run_sim_scenarioB_CSMA2(lambda_A, lambda_C ): 
    """Run the simulation at different lambdas"""
    simtime = 10e6 # time in microsecond, 10 seconds

    #generate the Frames to be sent of the simulation
    a2b = [Frame("A", "B", slot) for slot in poisson_distribution(Lambda=lambda_A) ]
    c2b = [Frame("C", "B", slot) for slot in poisson_distribution(Lambda=lambda_C) ]
    
    #start the counter class
    counter = Counter(1e10)

    #Connection class simulates the shared medium. 
    conn = Connection(counter)

    #The stations connected to the shared medium.
    A = Station( conn , 'A', a2b, True )
    B = Station( conn , 'B', [], True )
    C = Station( conn , 'C', c2b, True )
    #D = Station( conn , 'D', [], True )

    #make the stations global for convienience. 
    global stations
    stations = (A, B, C)

    #count up in micro seconds stop at 10 seconds. 
    for cnt in counter:
        if cnt > simtime:
            break
        
        data = conn.get( block=False )
        for station in stations:
            station.one_loop()


        """
        print( cnt )
        print( conn.inTransit )
        print( counter.status() )
        print( B.tosend_frames )
        """

    for station in stations:

        print("{} success:{}, collisions:{} Throughput {}".format( station, 
            station.success_count, 
            station.collision_count,
            station.success_count*Frame.size*8/(simtime/1e6)) )

    return { 
                "A":A.success_count*Frame.size*8/(simtime/1e6), 
                "C": C.success_count*Frame.size*8/(simtime/1e6),
                "Throughput":(A.success_count+C.success_count)*Frame.size*8/(simtime/1e6),
                "Collisions": A.collision_count,
                "Fairness":float(A.success_count)/C.success_count
                }






def main():


    
    
    outjson = {}
    for Lambda in (50, 100, 200, 300 ):
        #implementation 1
        outjson["CSMA1imp1scenA{}".format(Lambda)] = run_sim_scenarioA_CSMA1( Lambda, Lambda ) 
        outjson["CSMA2imp1scenA{}".format(Lambda)] = run_sim_scenarioA_CSMA2( Lambda, Lambda )
        outjson["CSMA1imp1scenB{}".format(Lambda)] = run_sim_scenarioB_CSMA1( Lambda, Lambda ) 
        outjson["CSMA2imp1scenB{}".format(Lambda)] = run_sim_scenarioB_CSMA2( Lambda, Lambda ) 


        #implementation 2 ( Lambda_A = 2*Lambda )
        outjson["CSMA1imp2scenA{}".format(Lambda)] = run_sim_scenarioA_CSMA1( 2*Lambda, Lambda ) 
        outjson["CSMA2imp2scenA{}".format(Lambda)] = run_sim_scenarioA_CSMA2( 2*Lambda, Lambda ) 
        outjson["CSMA1imp2scenB{}".format(Lambda)] = run_sim_scenarioB_CSMA1( 2*Lambda, Lambda ) 
        outjson["CSMA2imp2scenB{}".format(Lambda)] = run_sim_scenarioB_CSMA2( 2*Lambda, Lambda ) 


    
    json.dump( outjson, open("simulation.json", 'w') )





def throughput(station, imp, dname, indexname, data):

    row=0
    col=0
    
    if imp == "imp1":
        workbook  = xlsxwriter.Workbook("{}normal{}.xlsx".format( dname, station ) )
    elif imp == "imp2":
        workbook  = xlsxwriter.Workbook("{}2lamdba{}.xlsx".format( dname, station ) )

    worksheet = workbook.add_worksheet()
    worksheet.write_number( row, col, 1 )
    row+=1
    
    worksheet.write_number( row, col, 50 ) 
    worksheet.write_number( row, col+1, 100 )
    worksheet.write_number( row, col+2, 200 )
    worksheet.write_number( row, col+3, 300 )

    col=0
    row=0
    for CSMA in ( "CSMA1", "CSMA2" ):
        for scenario in ( "scenA", "scenB" ):
            row=0
            for Lambda in ( 50, 100, 200, 300 ):
                index = "{}{}{}{}".format( CSMA, imp, scenario, Lambda )
                #print("{} {} {}".format(index,  indexname, data[index][indexname]))
                print(row, col)
                worksheet.write_number( col+2, row, data[index][indexname] )
                #worksheet.add_number( row, col, data[index]["A"]  )
                row+=1
            col+=1


    

data = json.load( open( "simulation.json" ) )
for station in ( '', ):
   for imp in ( 'imp1', "imp2" ):
        throughput( station, imp, "Fairness", "Fairness", data )






    






