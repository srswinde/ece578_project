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

# time in micro seconds
SLOT = 20
SIFS = 10
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

 


class Station2:
    def __init__(self, medium, name, tosend_frames):
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
        

    def one_loop( self ):
        if self.backoff_countdown:
            if self.medium.isIdle():
                pass
            else:

                self.backoff_countdown.freeze()
        


        try:
            data = self.receiver.get(block=False)
        except Empty:
            data = None
        if data:
            if data.receiver == self.name:
                #data is for us
                if data == Frame:
                    self.received_frames.append(data)

                    self.medium.SIFS_countdown.start(SIFS, self.medium.put, Ack(data) )
                elif data == Ack:
                    if data == self.sent_frame:
                        self.sent_frame = None
                        self.success_count+=1


                    self.medium.DIFS_countdown.start(DIFS, self.medium.DIFS_finish )

            elif data == Collision:
                if self.sent_frame is None:
                    self.collision_count+=1




    def send (self ):
        if self.medium.isIdle():
            self.sent_frame = self.tosend_frames.pop(0)
            self.medium.put( self.sent_frame )



    def recv( self ):
        try:
            data = self.receiver.get()

        except:
            Emtpy
            data = None

        return data

    def __repr__( self ):
        return "Sation {}".format( self.name )

    def DIFS_finish( self ):
        if self.sent_frame:
            self.collision_count+=1
            self.sent_frame = None
        if len( self.tosend_frames ) > 0:
            if self.medium.counter.count > self.tosend_frames[0].slot:
                backoff = random.randint( 0, CW*self.backoff_multiplier )*SLOT
                if self.backoff_countdown:
                    self.backoff_countdown.unfreeze()
                else:
                    self.backoff_countdown.start( top=backoff, fxn=self.send )


    def SIFS_finish( self ):
        if self.ack:
            self.send(self.ack)
            self.ack = None





class Connection(Queue):
    """Connection class inherits from queue.
    Here we can overwrite the methods
    put and get. this will give us access
    to the receiving and transmitting. 
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
        """Overwrite the get part of the queue
        Here we check to see if there is an ack
        waiting for transmission. If so we transmit
        to the medium. If not we check for a 
        a data frame waiting to be transmitted. 
        The data frame and ack tranmissions are 
        triggered by the DIFS and SIFS trigger 
        function respectively"""

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
    size = 150


class RTS( Transmission ):
    pass

class CTS( Transmission ):
    pass

def poisson_distribution( Lambda=1, n=5 ):
    X = set() # set is handy for probability distributions

    for ITER in range(n):
        u = random.random() # random number between 0  and 1
        X.add((-1/Lambda)*math.log(1-u))
        
    return X





def main():
    
    A = Station( shared_medium, 'A' )
    B = Station( shared_medium, 'B' )
    C = Station( shared_medium, 'C' )
    D = Station( shared_medium, 'D' )
    
    A.start()
    B.start()
    C.start()
    D.start()

    counter = Counter()


    for cnt in counter:
        if cnt >  10000:
            break


    print( "Attempting to send" )
    A.send( "B" )
    #C.send( "D" )
    time.sleep( 5 )   

    A.kill()
    A.join()

    B.kill()
    B.join()

    C.kill()
    C.join()

    D.kill()
    D.join()

    shared_medium.kill()
    hared_medium.join()



def run_simulation(lambda_A, lambda_C ): 
    a2b = [Frame("A", "B", slot) for slot in poisson_distribution(Lambda=lambda_A, n=10000) ]
    c2d = [Frame("C", "D", slot) for slot in poisson_distribution(Lambda=lambda_C, n=10000) ]
    
    counter = Counter(1e10)

    conn = Connection(counter)
    conn.register( )
    A = Station2( conn , 'A', a2b )
    B = Station2( conn , 'B', [] )
    C = Station2( conn , 'C', c2d )
    D = Station2( conn , 'D', [] )


    global stations
    stations = (A, B, C, D)

    for cnt in counter:
        if cnt > 10e6:
            break
        
        data = conn.get( block=False )
        for station in stations:
            station.one_loop()

        """
        print( cnt )
        print( conn.inTransit )
        print( counter.status() )
        """
        #print(cnt )


    for station in stations:
        print("{} success:{}, collisions:{}".format(station, station.success_count, station.collision_count))

run_simulation(50, 2*50)





