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
            if data.receiver == self.name:
                #data is for us
                if data == Frame:
                    
                    self.received_frames.append(data)
                    self.medium.SIFS_countdown.start(SIFS, self.medium.put, Ack(data) )
                elif data == Ack:

                    print("we recved an ack ", data)
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

                        self.backoff_countdown.freeze()





            elif data == Collision:
                #Collision our data was not sent. 
                if self.sent_frame is None:
                    self.collision_count+=1
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

            else:
                self.clear_to_send = False
                if len( self.tosend_frames ) > 0:
                    if self.medium.counter.count > self.tosend_frames[0].slot:
                        backoff = random.randint( 0, CW*self.backoff_multiplier )*SLOT
                        if self.backoff_countdown:
                            self.backoff_countdown.unfreeze()
                        else:
                            self.backoff_countdown.start( top=backoff, fxn=self.send )

        else:#virtual sense
            if self.backoff_countdown:
                
                self.backoff_countdown.unfreeze()
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
        self.SIFS_countdown = count_down( top=None, name="SIFS", trigger_function = self.SIFS_finish )
        self.DIFS_countdown = count_down( top=None, name="DIFS", trigger_function = self.DIFS_finish )
        self.inTransit = None
        self.traverse_countdown = count_down(top=None, name="traverse", trigger_function=self.tx_arrive)
        self.DIFS_countdown.start(DIFS, self.DIFS_finish )

        self.secret_queue = Queue()

        self.counter = counter
        super().__init__()


    def register( self ):
        self.counter.register( self.traverse_countdown )
        self.counter.register( self.SIFS_countdown )
        self.counter.register( self.DIFS_countdown )

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
                station.receiver.put(data)

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
        print( "Collision" )
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


    def SIFS_finish( self ):
        print( "SIFS is over" )

    def inDIFS( self ):
        return bool( self.DIFS_countdown )

    def inSIFS( self ):
        return bool( self.SIFS_countdown )
    
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
        return "<TX sender: {} recver: {} tx_type:{} uuid:{}>".format(self.sender, self.receiver, self.tx_type, self.uuid)

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

    def __init__( self ):
        pass


class Ack( Transmission ):
    tx_type = "Ack"
    size = 30

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

    def __init__(self, rts):
        self.sender = rts.receiver
        self.receiver = rts.sender
        self.uuid = rts.uuid

def poisson_distribution( Lambda=1, n=5 ):
    X = set() # set is handy for probability distributions

    for ITER in range(n):
        u = random.random() # random number between 0  and 1
        X.add((-1/Lambda)*math.log(1-u))
        
    return X



def run_simulation_scenarioA(lambda_A, lambda_C ):
    """Run the simulation at different lambdas"""
    simtime = 10e6 # time in microsecond, 10 seconds

    #generate the Frames to be sent of the simulation
    a2b = [Frame("A", "B", slot) for slot in poisson_distribution(Lambda=lambda_A, n=100000) ]
    c2d = [Frame("C", "D", slot) for slot in poisson_distribution(Lambda=lambda_C, n=100000) ]
    
    #start the counter class
    counter = Counter(simtime*2)

    #Connection class simulates the shared medium. 
    conn = Connection(counter)
    conn.register( )

    #The stations connected to the shared medium.
    A = Station( conn , 'A', a2b, False)
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

        print( cnt )
        print( conn.inTransit )

        print( counter.status() )

    
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

def run_simulation_scenarioB(lambda_A, lambda_C ): 
    """Run the simulation at different lambdas"""
    simtime = 10e6 # time in microsecond, 10 seconds

    #generate the Frames to be sent of the simulation
    a2b = [Frame("A", "B", slot) for slot in poisson_distribution(Lambda=lambda_A, n=10000) ]
    c2d = [Frame("C", "B", slot) for slot in poisson_distribution(Lambda=lambda_C, n=10000) ]
    
    #start the counter class
    counter = Counter(1e10)

    #Connection class simulates the shared medium. 
    conn = Connection(counter)
    conn.register( )

    #The stations connected to the shared medium.
    A = Station( conn , 'A', a2b, True )
    B = Station( conn , 'B', [], True )
    C = Station( conn , 'C', c2d, True )
    D = Station( conn , 'D', [], True )

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


def test():

    run_simulation_scenarioA(50, 50)


def main():

    workbook_names = ["nodeA_scenarioA_implementation1", "nodeC_scenarioA_implementation1", "nodeA_scenarioB_implementation2", "nodeC_scenarioB_implementation2"]
    workbooks = {}
    worksheets = {}

    dataid = 1
    for wbname in workbook_names:
        workbooks[wbname] = xlsxwriter.Workbook("{}.xlsx".format(wbname))

        worksheets[wbname] = workbooks[wbname].add_worksheet()
        worksheets[wbname].write_number(0, 0 , dataid)
        dataid+=1
    row = 1
    col = 0

    

    outjson = []
    for (Lambda) in ( 50.0, 100.0, 200.0, 300.0 ):
            

        simdata = run_simulation( Lambda, Lambda ) 
        worksheets["nodeA_scenarioA_implementation1"].write_number( row, col, Lambda )
        worksheets["nodeC_scenarioA_implementation1"].write_number( row, col, simdata["A"] )


        worksheets["nodeC_scenarioA_implementation1"].write_number( row, col, Lambda )
        worksheets["nodeC_scenarioA_implementation1"].write_number( row, col, simdata["C"] )

        col+=1


        
    for nm in workbook_names:
        workbooks[nm].close()


    #for (Lambda) in ( 50.0, 100, 200.0, 300.0 ):

        #outjson.append( { "twolambda_onelambda":run_simulation( 2*Lambda, Lambda ) } )
    
        



test()
            


