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
    def __init__(self, name, medium):
        self.medium = medium
        self.name = name
        self.receiver = Queue()
        self.backoff_countdown = count_down( top=None, name="{} Back Off".format(self.__repr__()) )
        self.backoff_multiplier = 1
        self.sent_frames = []
        self.tosend_frames = []
        self.ack = None
        

    def one_loop( self ):
        if not self.medium.isIdle():
            self.backoff_countdown.freeze()
        else:
            self.backoff_countdown.unfreeze()

        data = self.recv()
        if data.receiver == self.name:
            #data is for us
            if data == Frame:
                self.frames.append(data)
                self.ack = Ack(self.name, data.sender)

            elif data == Ack:
                self.frames.remove(data)

    def acknowledge( self, frm ):
        pass


    def send(self, receiver):
        self.tosend_frames.append(Frame(self.name, receiver))

    def transmit( self ):

        self.medium.put( self.tosend_frames.pop(0) )

    def recv( self ):
        try:
            data = self.receiver.get()

        except:
            Emtpy
            data = None

        return data

    def __repr__( self ):
        return "Sation {}".format( self.name )

    def DIFS_trigger( self ):
        if len( self.tosend_frames ) > 0:
            backoff = random.randint( 0, CW*self.backoff_multiplier )*SLOT
            self.backoff_countdown.start( backoff, self.send )

    def SIFS_trigger( self ):
        if self.ack:
            self.send(self.ack)
            self.ack = None



class Station( Thread ):
    """The nodes of the network"""
    running = False
    def __init__( self, medium, name ):
        super().__init__()
        self.medium = medium
        self.name = name
        self.receiver = Connection()
        self.sender = Connection( self )
        self.status = None
        self.ack = None
        self.ack_transmit = False
        self.back_off = 0
        self.back_off_multiplier = 1
        self.back_off_countdown = count_down(CW, "Sation {} Back Off".format(name), self.transmit)
        self.medium.register( self )
        self.sent_frames = []

    def run( self ):
        self.running = True
        
        while self.running:
            time.sleep(0.001) #Give the processer breathing room. 

            self.check_medium_to_freeze()

            rx = self.recv()
            if rx:
                if rx.tx_type == "Frame":
                    self.ack = Ack( rx.receiver, rx.sender )
                elif rx.tx_type == "Ack":
                    rm = None
                    print("{} received Ack {}".format(self.__repr__(), rx) )

                    for ii in range(len(self.sent_frames)):
                        if rx.uuid == self.sent_frames[ii]:
                            rm = ii
                            break
                    if rm:
                        self.sent_frames.pop(rm)




    def __repr__(self):
        return "<Station {}>".format(self.name)

    def recv( self ):
        try:
            tx = self.receiver.get( block=False )
        except Empty:
            tx = None
        if tx is not None:
            if tx.receiver is not self.name:
                #its not for us throw it away
                tx = None

        return tx

    def check_medium_to_freeze( self ):

        """if we are planning to transmit and 
        the medium becomes not idle freeze
        the countdown"""
        if not self.medium.idle:
            if self.back_off_countdown:
                self.back_off_countdown.freeze()
        else:
            self.back_off_countdown.unfreeze()



    def send(self, station):
        # put the frame in the send queue
        self.sender.put( Frame( self.name, station ), False )


    def kill(self):
        self.running = False

    def transmit(self):

        self.sender.transmit = True

    def DIFS_trigger(self):
        if not self.sender.empty():
            
            back_off = random.randint( 0, CW*self.back_off_multiplier )*SLOT
            if back_off < SLOT:
                print("BACK_OFF is {}".format(back_off), file=sys.stderr)
            self.back_off_countdown.start( back_off )

    def SIFS_trigger(self):
        if self.ack:
            self.sender.put(self.ack)
            self.ack = None
            self.ack_transmit=True


class Medium( Thread ):
    """The shared medium inherits from Thread
    this will watch over the communication
    channel and simulate the collisions or 
    successfull transmissions
    """

    running = False

    def __init__(self):

        super().__init__()
        self.stations = None

        self.DIFS_countdown = count_down( DIFS, "DIFS", self.DIFS_trigger )
        self.SIFS_countdown = count_down( SIFS, "SIFS", self.SIFS_trigger )
        self.Traverse_countdown = count_down(10, "TRAVERSE")

        self.counter= Counter( 5000, self.DIFS_countdown, self.SIFS_countdown, self.Traverse_countdown )

        self.idle = True


    def DIFS_trigger(self):
        if self.stations:
            for st in self.stations:
                st.DIFS_trigger()

    def SIFS_trigger( self ):
        if self.stations:
            for st in self.stations:
                st.SIFS_trigger()

    def register( self, station ):
        """Each station should register with the common medium
        so the medium can handle its data traffic."""
        if self.stations is None:
            self.stations = []

        self.counter.register( station.back_off_countdown )
        self.stations.append( station )


    def run(self):
        """Most of the important timekeeping etc is done here.
        In the while self.running block. Each loop is 
        1 micro second and will count down the various
        timers before handling the transmission
        """

        self.running = True
        first_loop = True
        for count in self.counter:
            time.sleep(0.001)

            if count == None:
                break

            if self.counter.first_loop:
                self.DIFS_countdown.start()
                
            


            if self.stations is None:
                    #Nobdody has registered
                    
                    continue

            if self.DIFS_countdown: # In Difs state
                continue

            elif self.SIFS_countdown: # In SIFS state
                continue

            elif self.Traverse_countdown: # Waiting for tx to traverse medium
                self.idle = False
                #we don't continue here because we want to look for collisions
        
            else:
                self.idle = True
                
            communication_tally = []
            for station in self.stations:
                try:
                    tx = station.sender.get(block = False)
                except Empty:
                    tx = None

                
                if tx:
                    communication_tally.append(tx)
            if len( communication_tally ) > 1: 
                #two communications came in at same time
                # probably due to same back off time.
                                               
                print("We have a collision, same back off", communication_tally)

            elif self.Traverse_countdown and len(communication_tally) == 1 :

                print("We have a collision")
                
            elif len(communication_tally) == 1:
                print("comm tally is", communication_tally)
                self.traverse_medium(communication_tally[0])
            

            


    def traverse_medium( self, frm ):
        tx_time_s = frm.size*8/TX_RATE 
        tx_time_microseconds = tx_time_s*1e6

        print("{} is traversing".format(frm))
        self.Traverse_countdown.start( tx_time_microseconds, self.connect_the_pipe, frm )

    def connect_the_pipe(self, frm):
        for station in self.stations:

            station.receiver.put(frm)
        self.SIFS_countdown.start( SIFS )

    def kill(self):
        self.running = False
        self.counter.kill()




class Connection(Queue):
    """Connection class inherits from queue.
    Here we can overwrite the methods
    put and get. this will give us access
    to the receiving and transmitting. 
    """


    def __init__( self ):
        self.traverse_countdown = count_down( top=None, name="Traverse" )
        self.SIFS_countdown = count_down( top=None, name="SIFS" )
        self.DIFS_countdown = count_down( top=None, name="DIFS" )
        self.inTransit = None
        self.DIFS_countdown.start(DIFS, self.DIFS_finish )


        self.secret_queue = Queue()


        super().__init__()


    def register( self, counter ):
        counter.register( self.traverse_countdown )
        counter.register( self.SIFS_countdown )
        counter.register( self.DIFS_countdown )

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

            if data == Ack:
                self.DIFS_countdown.start( top=SIFS )

            elif data == Frame:
                self.DIFS_countdown.start( top=DIFS )
                


        try:
            data = super().get( *args, **kwargs )
        except Empty:
            data = None

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

                self.traverse_countdown.start( tx_time_microseconds, self.collision_arrive )

            self.inTransit = data
        return None
        


    def put( self, msg, *args, **kwargs ):
        super().put( msg, *args, **kwargs )

    def tx_arrive( self, data ):
        self.secret_queue.put( data )

    def collision_arrive( self ):
        print( "Collision" )
        self.secret_queue.put( Collission() )

    def isIdle( self ):

        if self.inDIFS():
            return False
        elif self.inSIFS():
            return False
        elif self.traverse_countdown:
            return False

        else:
            return True

    def DIFS_finish(self):
        print("DIFS is over")

    def SIFS_finish(self):
        print("SIFS is over")

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
        if self.inTransit:
            outstr+=str(self.iinTransit)
        return outstr


class Transmission():
    """Place holder for anything that 
    is methods and members common to 
    acks and frames"""
    def __init__( self, sender, receiver ):
        self.sender = sender # address or name of sender.
        self.receiver = receiver #address or name of receiver.
        self.uuid = uuid.uuid4()

    def __repr__( self ):
        return "<Frame sender: {} recver: {} tx_type:{}>".format(self.sender, self.receiver, self.tx_type)

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

    def __init__( self ):
        self.sender = None
        self.receiver = None


class Ack( Transmission ):
    tx_type = "Ack"
    size = 30

class Frame( Transmission ):
    tx_type = "Frame"
    size = 1500

class RTS( Transmission ):
    pass

class CTS( Transmission ):
    pass

def poisson_distribution( Lambda=1, n=5 ):
    X = set() # set is handy for probability distributions

    for ITER in range(n):
        u = random.random() # random number between 0  and 1
        X.add((-1/Lambda)*math.ln(1-u))
        
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



def main2(): 

    conn = Connection()
    A = Station2( conn , 'A' )
    B = Station2( conn , 'B' )
    C = Station2( conn , 'C' )
    D = Station2( conn , 'D' )

    counter = Counter(30000)
    
    conn.register( counter )

    f=Frame("A", "B")
    A.send("C")
    for cnt in counter:
        if cnt > 10000:
            break
        print( cnt, conn.status() )
    

main2()





